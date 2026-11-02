# FDGCast 1.0.4

This update makes disconnected activity feeds easier to notice, fixes destination
names collapsing into a one-letter column, and includes explicit software
licensing in the repository and Windows installer.

## Activity connection visibility

- A persistent status banner above the OBS Combined Activity Feed shows whether
  the activity connection is ready or needs attention. It stays visible even
  when saved activity cards are present and the optional dock status is hidden.
- Twitch chat connectivity is checked separately from event-subscription
  readiness. Missing event permissions and disconnected transports are visible.
- Companion's Activity Feed shows the same status, the individual platform
  details, and a direct button to Connections.
- Companion/bridge outages show an explicit disconnected warning. Old activity
  is history; it is not evidence of a working connection. Quiet feeds alone are
  not treated as disconnected. Missed events are not automatically recovered.
- Readiness covers the supported Twitch, YouTube and experimental TikTok activity
  readers. Other platforms' chat connections are not advertised as activity feeds.

## Destination layout

Destination names retain readable width. Start, Stop, Edit, Remove and additional
output controls wrap below destination details on desktop and narrow layouts.

## Licensing

Original FDGCast code is GPL-2.0-or-later. The bundled Companion uses the GPLv3-or-
later option for its Apache-2.0 combination; upstream components retain their
licenses. See LICENSE, COPYING.GPL3 and LICENSING.md. The installer includes those
texts, the corresponding-source link, collected dependency notices and an
exact-version inventory. The license does not restrict GPL modification rights
or grant access to independently operated paid Hub services. Existing official
subscription checks and paid overlay entitlements are unchanged.

## Installation and limits

Windows x64; built against OBS Studio 32.2.2. Close OBS and Companion before
installing. Saved settings and protected credentials are preserved. No automatic
stream starts, output routing changes or in-stream updates are introduced.

TikTok remains experimental, unofficial and receive-only, needs a public LIVE,
and has not been verified against a real LIVE for this release. Twitch follows
and other events depend on authorization scopes and platform eligibility.
Facebook/Instagram require separately configured Hub/Meta support. Existing
hardware/platform limits for Twitch dual format still apply.
