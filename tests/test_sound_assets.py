"""Check the shipped WAV files without playing sound on the developer's PC."""
import unittest
import wave

from src.services.sound import SoundService


class SoundAssetTests(unittest.TestCase):
    def test_both_sound_modes_resolve_to_readable_nonempty_pcm_audio(self) -> None:
        service = SoundService()
        for path in (service.paper_sound_path, service.trash_sound_path):
            with self.subTest(path=path.name), wave.open(str(path), "rb") as audio:
                self.assertEqual(audio.getcomptype(), "NONE")
                self.assertGreater(audio.getnframes(), 0)
                self.assertGreater(audio.getframerate(), 0)
                self.assertTrue(audio.readframes(1))
