# FDGCast 1.0.0

Windows x64 · OBS Studio 32.2.2

## Included

- Combined Twitch, YouTube and Kick chat/events, receive-only Rumble chat,
  experimental TikTok chat, and Facebook/Instagram Hub integration.
- Multistream destinations with independent horizontal/vertical picture choices.
- Dedicated Vertical Studio: large horizontal and portrait previews, camera crop
  drawing/moving/resizing, seven presets, customizable regions, saved per-scene
  layouts and prominent default-on scene following. Existing scene crops avoid
  opening another camera capture; lower GPU usage is not guaranteed.
- Main stream picture selection for whichever service is configured in OBS.
  No duplicate stream key is needed. Horizontal and Studio destinations can
  run simultaneously, with Studio outputs sharing their matching encoder.
- Stream Doctor, Audio Guard, preflight checks, backups and local diagnostics.
- Saved Overlay Studio designs, emoji effects and separate revocable OBS URLs.
  Core chat stays free; live overlays require verified paid/complimentary Hub access.
- Clearer setup, tooltips, event visibility and optional chat badges.

## Install and use

1. Close OBS and FDGCast Companion, then run the Windows x64 installer.
2. Open OBS and Companion. Existing settings, protected keys, pairing and designs
   use the existing data directory; this build does not migrate or reset them.
3. Connect OBS in Connections. In Vertical Studio, choose a layout, mark your
   camera on the horizontal scene and save.
4. In Destinations, choose the picture for **OBS main stream** and click
   **Apply main stream picture** while stopped. Wait for the Applied status.
   Other destinations have their own picture choices. Start OBS normally or
   use Start All with checked destinations. Each output sends one picture.

## Known limitations and follow-up checks

- Real creator broadcasts, reconnect/network-loss behavior, upgrade preservation,
  dock behavior and viewer picture/audio acceptance remain unverified. The owner
  accepted these as follow-up checks rather than release blockers.
- Vertical main output requires standard RTMP/RTMPS, H.264/AAC and Enhanced
  Broadcasting / multitrack video off. Open Companion first to sync saved layouts.
  Main service, audio/VOD tracks, recording settings and OBS canvas are preserved.
  Stop the main stream before changing its picture. Vertical is 720 × 1280 at
  4500 kbps and still consumes rendering/encoding capacity and upload bandwidth.
- Facebook and Instagram need the separately deployed/configured Meta Hub,
  supported accounts/permissions and any required review. Desktop installation
  alone does not enable them. Their live delivery is not claimed verified.
- Rumble needs the creator's private LiveStream API connection; polling can miss
  messages on busy streams. TikTok uses an unofficial experimental reader and
  can break when TikTok changes. Platform streaming eligibility still applies.
- Paid overlay entitlement delivery, revocation and OBS resource acceptance
  against the deployed Hub remain to be confirmed.
- Automatic face tracking, blur backgrounds, independent vertical audio and
  animated ending credits remain future work. No performance benchmark is claimed.

## Validation and downloads

The RC5 feature set passed 240 Python tests, native geometry/routing tests,
OBS 32.2.2 compilation, four browser suites, packaged startup and installer checks.
Stable 1.0.0 receives the same workflow before publication. Its release assets
include the installer, SHA256SUMS.txt and latest.json with the actual binary hash.

Official release: https://github.com/Dakotalamb/ForgeCast/releases/tag/v1.0.0

The Hub updater reads `/fdgcast/releases/latest.json` from the configured Hub.
Publishing the GitHub release does not deploy that Hub endpoint. Copy the exact
published latest.json there after the installer is public; until then existing
installs may continue showing the older hosted preview. See UPDATES.md.
