"""Actual Qt thread/event-loop tests with fake OS, tray and network services."""
from contextlib import ExitStack
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from src.core.background import TaskResult
from src.core.i18n import I18n
from src.core.settings import DEFAULT_SETTINGS
from src.core.updater import UpdateInfo
from src.services.recycle_bin import BinClearResult, RecycleBinInfo, RecycleBinService
from src.ui.tray.tray_app import TrayApp


def make_controller(stack, *, available=True, auto_check=True):
    settings = SimpleNamespace(**{**DEFAULT_SETTINGS, 'auto_check_updates': auto_check})
    settings.set = Mock()
    settings.get = lambda key, default=None: getattr(settings, key, default)
    recycle = Mock(get_info=Mock(return_value=RecycleBinInfo(0, 0, available)),
                   level_from_metrics=RecycleBinService.level_from_metrics)
    updater = Mock(has_update=False, info=None, just_updated=False, last_error='')
    stack.enter_context(patch('src.ui.tray.tray_app.RecycleBinService', return_value=recycle))
    stack.enter_context(patch('src.ui.tray.tray_app.AutostartService', return_value=Mock(is_enabled=lambda: False)))
    stack.enter_context(patch('src.ui.tray.tray_app.Updater', return_value=updater))
    stack.enter_context(patch('src.ui.tray.tray_app.SoundService', return_value=Mock()))
    stack.enter_context(patch.object(TrayApp, '_ensure_tray_visible'))
    callbacks = []
    with patch('src.ui.tray.tray_app.QTimer.singleShot', side_effect=lambda delay, cb: callbacks.append((delay, cb))):
        controller = TrayApp(settings, I18n('RU'))
    stack.enter_context(patch.object(controller.tray, 'showMessage'))
    controller._test_callbacks = callbacks
    return controller


class AppLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.stack = ExitStack()
        self.controller = make_controller(self.stack)
        self.wait_idle()

    def wait_idle(self):
        deadline = time.monotonic() + 3
        while self.controller._task_runner.busy and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertFalse(self.controller._task_runner.busy)

    def tearDown(self):
        c = self.controller
        for timer in (c.timer, c.update_timer, c._tray_retry_timer, c._apply_timer, c._shutdown_timer):
            timer.stop()
        c._shutting_down = True
        c._task_runner.wait()
        self.app.processEvents()
        if c._about_dialog:
            c._about_dialog.close()
            c._about_dialog.deleteLater()
        c.menu.close()
        c.menu.deleteLater()
        c.deleteLater()
        self.app.processEvents()
        self.stack.close()

    def test_statistics_run_off_gui_thread_and_do_not_overlap(self):
        c = self.controller
        worker_threads = []
        def slow_read():
            worker_threads.append(threading.get_ident())
            time.sleep(.15)
            return RecycleBinInfo(0, 0)
        c.recycle_bin.get_info.side_effect = slow_read
        ticks = []
        timer = QTimer()
        timer.setInterval(5)
        timer.timeout.connect(lambda: ticks.append(1))
        timer.start()
        c._refresh_state()
        for _ in range(10):
            c._refresh_state()
        self.wait_idle()
        timer.stop()
        self.assertEqual(len(worker_threads), 1)
        self.assertNotEqual(worker_threads[0], threading.get_ident())
        self.assertGreater(len(ticks), 5)

    def test_result_and_progress_callbacks_run_on_gui_thread(self):
        threads = []
        results = []
        self.controller._task_runner.start(
            lambda emit: (emit(50), threading.get_ident())[-1],
            lambda result: (threads.append(threading.get_ident()), results.append(result)),
            lambda value: threads.append(threading.get_ident()),
        )
        self.wait_idle()
        self.assertEqual(threads, [threading.get_ident()] * 2)
        self.assertNotEqual(results[0].value, threading.get_ident())

    def test_query_failure_keeps_fallback_icon(self):
        c = self.controller
        c.recycle_bin.get_info.return_value = RecycleBinInfo(0, 0, False)
        c._refresh_state()
        self.wait_idle()
        self.assertFalse(c.tray.icon().isNull())
        self.assertEqual(c.tray.toolTip(), c.i18n.tr('tooltip_unavailable'))

    def test_startup_callback_honors_disabled_auto_check(self):
        c = self.controller
        c.settings.auto_check_updates = False
        next(cb for delay, cb in c._test_callbacks if delay == 5000)()
        c.updater.check_for_update.assert_not_called()
        c.settings.auto_check_updates = True
        c.updater.check_for_update.return_value = None
        next(cb for delay, cb in c._test_callbacks if delay == 5000)()
        self.wait_idle()
        c.updater.check_for_update.assert_called_once_with(force=False)

    def test_download_does_not_race_with_check(self):
        c = self.controller
        c._update_check_in_progress = True
        c._start_update_download(UpdateInfo('v9', '', '', '', 0))
        self.assertFalse(c._update_download_in_progress)
        c.updater.download_update.assert_not_called()

    def test_completed_download_waits_for_clear_before_async_apply(self):
        c = self.controller
        c._clear_in_progress = True
        c._update_download_in_progress = True
        c._on_update_download_finished(TaskResult(value=('fixture.exe', '')))
        c._maybe_apply_update()
        c.updater.apply_update.assert_not_called()
        self.assertEqual(c._pending_update_path, Path('fixture.exe'))
        c._clear_in_progress = False
        c.updater.apply_update.return_value = True
        with patch.object(c, 'quit_app') as quit_app:
            c._maybe_apply_update()
            self.wait_idle()
            quit_app.assert_called_once()
        c.updater.apply_update.assert_called_once_with(Path('fixture.exe'))

    def test_apply_failure_restores_controls(self):
        c = self.controller
        c._pending_update_path = Path('fixture.exe')
        c.updater.apply_update.return_value = False
        c.updater.last_error = 'fixture denied'
        with patch.object(c, '_show_error') as show_error:
            c._maybe_apply_update()
            self.wait_idle()
            self.assertIn('fixture denied', show_error.call_args.args[0])
        self.assertTrue(c.clear_action.isEnabled())
        self.assertTrue(c.check_updates_action.isEnabled())
        self.assertFalse(c._update_apply_in_progress)

    def test_quit_waits_without_blocking_event_loop_or_starting_more_tasks(self):
        c = self.controller
        release = threading.Event()
        c._task_runner.start(lambda _: release.wait(2), lambda _: None)
        with patch.object(self.app, 'quit') as quit_app:
            c.quit_app()
            QTest.qWait(80)
            quit_app.assert_not_called()
            with self.assertRaises(RuntimeError):
                c._task_runner.start(lambda _: None, lambda _: None)
            release.set()
            self.wait_idle()
            QTest.qWait(80)
            quit_app.assert_called_once()

    def test_minimized_about_is_restored_by_menu_action(self):
        c = self.controller
        from src.ui.dialogs.about_dialog import AboutDialog
        c._about_dialog = AboutDialog(c.i18n)
        c._about_dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        with patch.object(c._about_dialog, 'activateWindow'):
            c.show_about()
            c._about_dialog.showMinimized()
            self.app.processEvents()
            self.assertTrue(c._about_dialog.isMinimized())
            c.show_about()
            self.app.processEvents()
            self.assertFalse(c._about_dialog.isMinimized())

    def test_partial_wipe_is_a_warning_not_unqualified_success(self):
        c = self.controller
        c._on_clear_task_finished(TaskResult(value=BinClearResult(True, 'zero', 0, 0, 2)))
        from PyQt6.QtWidgets import QSystemTrayIcon
        call = c.tray.showMessage.call_args.args
        self.assertEqual(call[2], QSystemTrayIcon.MessageIcon.Warning)
        self.assertIn('2', call[1])

    def test_autostart_failure_does_not_claim_it_was_disabled(self):
        c = self.controller
        c.autostart.set_enabled.return_value = False
        with patch.object(c, '_show_error') as show_error:
            c._on_autostart_toggled(False)
            show_error.assert_called_once_with(c.i18n.tr('error_autostart'))


class ShutdownProcessTests(unittest.TestCase):
    def test_real_process_exits_cleanly_with_pending_work_and_external_quit(self):
        code = '''
from contextlib import ExitStack
import sys, time
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from tests.test_app_lifecycle import make_controller
def main():
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    with ExitStack() as stack:
        controller = make_controller(stack)
        app._tray_app = controller
        controller._task_runner.start(lambda _: time.sleep(.2), lambda _: None)
        QTimer.singleShot(20, app.quit if sys.argv[1] == 'external' else controller.quit_app)
        try:
            return app.exec()
        finally:
            controller._task_runner.wait()
sys.exit(main())
'''
        for mode in ('normal', 'external'):
            with self.subTest(mode=mode):
                result = subprocess.run([sys.executable, '-c', code, mode],
                    cwd=Path(__file__).resolve().parents[1],
                    env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                    capture_output=True, timeout=10,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
