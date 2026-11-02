# Vertical platform setup

Create and save your scene layouts in Vertical Studio. Existing camera and game sources are reused; you do not need to open another camera capture.

| Platform | Route | What you need |
| --- | --- | --- |
| Twitch | OBS Additional Canvas + Enhanced Broadcasting | Twitch as the main OBS service, then select FDGCast Vertical Studio. No second key. |
| YouTube Horizontal + Vertical | Two encoder connections within one YouTube broadcast | Horizontal key for OBS picture; vertical preview set to Encoder with a second key for Vertical Studio. |
| TikTok LIVE | Portrait RTMP output | Server URL and stream key provided to your account by TikTok. LIVE Studio access and chat connection are separate. |
| Instagram Live | Portrait RTMP output | Eligible Live Producer access and current session URL/key. Complete publishing on Instagram. |
| Vimeo Live | Portrait RTMP output | Eligible live-event plan and event URL/key. Portrait output is not automatic dual format. |

Kick and unverified encoder destinations are excluded from FDGCast's portrait options. This is a conservative application support list, not a claim that every other platform rejects every portrait signal.

## Twitch

1. Stop streaming and recording. In Vertical Studio select **Enable FDGCast canvas in OBS**.
2. Open **OBS → Settings → Stream**. Set the service to Twitch and enable **Enhanced Broadcasting**.
3. Select **FDGCast Vertical Studio** under **Additional Canvas**, then Apply. Reopen Settings if it was already open when the canvas was created.
4. Under Multitrack Video, set **Maximum Video Tracks** to at least **4**. Two canvases require at least two video tracks each. If the same error persists, inspect the OBS log for GPU/encoder limits. For horizontal-only streaming, select **None** for Additional Canvas.
5. Save your scene layouts. **Start Streaming** in OBS sends both pictures together. Start All also starts checked destinations.
6. Check Twitch Inspector and actual mobile playback. A configured status does not prove platform delivery.

The canvas is saved with the OBS scene collection and restored at startup. Stop video outputs before changing or disabling it. To disable, select **None** for Additional Canvas in OBS first. The main encoder is not replaced. The portrait canvas does not mix another copy of audio; OBS's stream audio is used.

## YouTube

Use **YouTube Horizontal** with the horizontal key and OBS picture. Add **YouTube Vertical** with the separate key from the vertical preview after selecting **Encoder**. Keep the OBS picture landscape if that destination is intended for widescreen viewing. Both feeds share the YouTube broadcast and chat. Auto crop is YouTube's alternative when only the horizontal feed is sent.

## Account access and resources

A stream-key field or preset cannot grant platform access. TikTok must expose encoder credentials; no fixed follower threshold is assumed. Instagram session keys can change. Vimeo live-plan access is required. Chat authorization does not authorize video publishing.

FDGCast's separate portrait outputs use 720×1280, inherit the OBS frame rate, and target 4500 kbps. Twitch Enhanced Broadcasting selects its own encoding parameters. Reusing sources and the portrait render reduces duplication, but additional video encodes and uploads still require GPU/CPU and bandwidth headroom. Review Stream Doctor and platform previews.

## Evidence and limits

Platform source links and verification scope are recorded in VERTICAL_PLATFORM_CHECKPOINT.md. Validation of native encoding and canvas registration is separate from real account playback. Hardware encoder limits, reconnects and platform-specific account eligibility need operator checks.
