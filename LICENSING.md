# FDGCast licensing

Copyright (C) 2026 Daniel Lamb and FDGCast contributors.

Except for third-party material identified below, FDGCast's original source code
in this repository is licensed under the GNU General Public License as published
by the Free Software Foundation, either version 2 of the License, or (at your
option) any later version (SPDX: GPL-2.0-or-later).

FDGCast is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See LICENSE for the complete GNU GPL version 2 text.
COPYING.GPL3 contains the complete GNU GPL version 3 text.

## Components and combined distributions

- Original native OBS module source: GPL-2.0-or-later. OBS and Qt retain their
  respective licenses; this project does not relicense either dependency.
- Original Companion, web interface and build scripts: GPL-2.0-or-later.
- The distributed Companion combines that code with Apache-2.0 components,
  including Google's YouTube protocol sample and dependencies. For that combined
  work, the GPL version 3-or-later option applies, since Apache-2.0 is compatible
  with GPLv3, not GPLv2-only. Third-party components retain their own notices and
  licensing terms. See COPYING.GPL3 and the installed licenses directory.
- forgecast/youtube_proto retains its Apache-2.0 LICENSE.txt and NOTICE.txt.
- TikTokLive 7.0.1 and TikTokLiveProto carry AGPLv3 text with additional
  library-integration permissions. Their full, unmodified licenses are included
  in the dependency notices. This release uses them only in the local desktop
  reader, not a hosted TikTok relay or SaaS API. Their exception has different
  conditions for hosted/network services; review the upstream terms before
  moving the reader to a server.
- Python, Python runtime packages, pywebview, PyInstaller's bootloader and other
  bundled material retain their upstream licenses and applicable exceptions.
  The Windows build collects installed dependency license/notice files and an
  exact-version inventory in licenses/third-party. This is not a relicensing of
  those dependencies. Build tools that are not shipped are separate.

## Corresponding source

Each release is built from the commit identified by its GitHub tag. Its source,
including build scripts and dependency versions, is available from:
https://github.com/Dakotalamb/ForgeCast/releases

For this release: https://github.com/Dakotalamb/ForgeCast/tree/v1.0.4
Download the matching tag's source archive, not a potentially older default
branch. The official installer includes these license texts and the source link.
Upstream source locations for packaged Python distributions are recorded in the
third-party inventory. Source and license obligations for redistributed
third-party binaries continue to apply.

## Subscriptions and services

The official FDGCast distribution may require verified paid or complimentary
Hub access for optional features. These subscription checks do not add
restrictions to the GPL rights granted for covered code, including modification
and redistribution. A modified local client does not grant access to separately
operated Hub accounts, paid services or infrastructure.

This license covers the code in this repository. It does not automatically
license a separate Hub/server repository. Licensing of independent services must
be assessed separately. Branding and third-party platform marks are not granted
an endorsement by this code license. Nothing here limits rights granted by the
GPL in covered material.
