"""Bounded PCM WAV validation and local Audio Guard playback."""
import asyncio
import io
import math
import os
import struct
import wave

MAX_BYTES = 2_000_000


def read_pcm(data):
    if not isinstance(data, bytes) or len(data) > MAX_BYTES:
        raise ValueError('Choose a WAV under 2 MB, up to five seconds long.')
    try:
        with wave.open(io.BytesIO(data), 'rb') as source:
            channels, width, rate, frames = source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getnframes()
            if source.getcomptype() != 'NONE' or channels not in (1, 2) or width not in (1, 2) or not 8000 <= rate <= 48000 or not 0 < frames <= rate * 5:
                raise ValueError('Use an 8-bit or 16-bit PCM WAV, mono/stereo, up to five seconds (8–48 kHz).')
            pcm = source.readframes(frames)
            if len(pcm) != frames * channels * width:
                raise ValueError('The WAV is incomplete.')
            return channels, width, rate, pcm
    except (wave.Error, EOFError) as exc:
        raise ValueError('Choose an uncompressed PCM WAV file.') from exc


def pack_pcm(channels, width, rate, pcm):
    target = io.BytesIO()
    with wave.open(target, 'wb') as output:
        output.setnchannels(channels); output.setsampwidth(width); output.setframerate(rate); output.writeframes(pcm)
    return target.getvalue()


def default_chirp():
    rate = 16000
    samples = []
    for frequency, duration in [(660, .18), (0, .07), (880, .24)]:
        count = round(rate * duration)
        for i in range(count):
            envelope = math.sin(math.pi * i / count) ** 2
            samples.append(round(16000 * envelope * math.sin(2 * math.pi * frequency * i / rate)))
    return pack_pcm(1, 2, rate, struct.pack('<' + 'h' * len(samples), *samples))


def scaled_wav(data, volume):
    if isinstance(volume, bool) or not isinstance(volume, (int, float)) or not math.isfinite(volume) or not 0 <= volume <= 100:
        raise ValueError('Sound volume must be between 0 and 100.')
    channels, width, rate, pcm = read_pcm(data)
    gain = volume / 100
    if width == 2:
        values = [round(value[0] * gain) for value in struct.iter_unpack('<h', pcm)]
        pcm = struct.pack('<' + 'h' * len(values), *values)
    else:
        pcm = bytes(round((value - 128) * gain) + 128 for value in pcm)
    return pack_pcm(channels, width, rate, pcm)


async def play_sound(custom_path, volume=45):
    if os.name != 'nt': return False
    import winsound
    try:
        data = custom_path.read_bytes() if custom_path.exists() else default_chirp()
        data = scaled_wav(data, volume)
        # Memory WAV playback must be synchronous; run off the event loop.
        await asyncio.to_thread(winsound.PlaySound, data, winsound.SND_MEMORY)
        return True
    except (OSError, RuntimeError, ValueError):
        return False
