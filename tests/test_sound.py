import io
import struct
import unittest
import wave
from forgecast.sound import default_chirp, read_pcm, scaled_wav, pack_pcm

class SoundTests(unittest.TestCase):
    def test_chirp_is_short_valid_pcm_and_gain_is_local(self):
        original=default_chirp()
        channels,width,rate,pcm=read_pcm(original)
        self.assertEqual((channels,width,rate),(1,2,16000))
        self.assertLess(len(pcm)/(width*rate),1)
        self.assertNotEqual(set(pcm),{0})
        self.assertEqual(set(read_pcm(scaled_wav(original,0))[3]),{0})
        half=read_pcm(scaled_wav(original,50))[3]
        for before,after in zip(struct.iter_unpack('<h',pcm),struct.iter_unpack('<h',half)):
            self.assertLessEqual(abs(after[0]-before[0]/2),.5)
        self.assertEqual(original,default_chirp())

    def test_reject_invalid_wav_duration_volume_and_truncated_pcm(self):
        for bad in [b'not a wav',b'X'*2000001,pack_pcm(1,2,8000,b'\0'*96000),default_chirp()[:-4]]:
            with self.assertRaises(ValueError):read_pcm(bad)
        for volume in [-1,101,True,float('nan')]:
            with self.assertRaises(ValueError):scaled_wav(default_chirp(),volume)

    def test_unsigned_eight_bit_silence_is_centered(self):
        sound=pack_pcm(1,1,8000,bytes([0,128,255])*100)
        self.assertEqual(set(read_pcm(scaled_wav(sound,0))[3]),{128})
