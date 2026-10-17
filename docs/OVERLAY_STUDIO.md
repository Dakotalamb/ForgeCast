# Overlay Studio — scope for 0.9.0 Preview

## Saved designs

Create up to sixteen named designs, with up to twelve positioned widgets each.
Each design saves its canvas dimensions and reduced-motion choice. Widgets offer
position, dimensions, font/emote size, colors, background opacity, display duration,
maximum items, platform filters and an enabled switch.

Widgets currently implemented:

- Chat: recent public messages with platform emote fragments when available.
- Emote effects: Unicode emoji and supported chat emote images; float, rain or burst.
- Activity alerts: events already received by the existing platform integrations.
- Text/heading: plain text with configurable styling; no arbitrary HTML/scripts.
- Manual goal: editable label/current/target and progress bar; no invented audience totals.

Save updates the same design and keeps its OBS URL stable. Duplicate creates a new
independent design. Export/import contains design data only, with no credentials or
URLs. Each design has its own token; rotate or delete revokes that design's links
without affecting other saved designs.

Sample preview includes labelled sample events and chat. Live data is never included
in an unpaid sample preview. Drag widgets in the saved preview, then save to apply
new positions. The form also supports precise positions and dimensions.

## OBS setup and resource choices

Use a design's live URL in an OBS Browser Source. Set dimensions to the design's
canvas (for example 1920×1080), choose 30 FPS, and enable “Shutdown source when not
visible.” Add the source above gameplay. Companion must be running on the same PC.

A combined design renders several widgets through one Browser Source. Use separate
design URLs when you need independent OBS transforms, layer ordering or visibility.
One combined source generally avoids the overhead of several browser renderers;
actual OBS resource usage still requires measurement on a real stream.

The player uses built-in DOM/CSS/Web Animations with no animation framework or
continuous JavaScript frame loop. It stops delivery and clears effects when browser
or OBS visibility callbacks report it hidden. Emote animations are bounded to sixty
per widget and 120 total per design. Reduced motion caps these at eight and 32 and
uses fades. Static designs check for updates every five seconds; dynamic designs
check once per second. Messages/events are bounded and deduplicated, with no replay
of old live effects at initial load. Cooldowns prevent repeated emote bursts.

## Paid access — required website handoff

Recommendation: include live overlays in Supporter, preserving complimentary access
for official FDG creators, administrators and existing valid grants. Future Business
plans can grant the same feature flag. The website owns the tier mapping and billing;
no price or new checkout is configured by the desktop app.

The website builder must add this top-level field to the **existing authenticated**
`GET /api/forgecast/v1/connections` response:

```json
{"entitlements":{"fdgcast_overlays":true},"connections":[]}
```

The example's empty connections list is illustrative; preserve the existing linked
account response. Compute this boolean through the Hub's shared entitlement service,
using the paired integration token's owner. Never accept a creator-supplied plan or
feature flag. Blocked users, revoked integrations and accounts without eligible
access must not receive a true flag. On eligibility loss return false. Include active
paid access, official FDG complimentary membership, admin access and valid grants
according to the current Hub rules. Do not activate paid Business checkout implicitly.

Companion reads this flag on each existing account sync. Only a literal true grants
access. Verified access has a bounded fifteen-minute in-memory connection-loss grace;
an explicit false removes access immediately. Restart requires a fresh verification.
Local preferences cannot grant it. Until the Hub ships this field, live overlays
remain locked; unrelated chat and multistream features continue to work.

Both legacy chat overlays and new design feeds enforce the live gate. The designer,
saved drafts and sample preview remain usable without paid access. Cancelling/losing
access retains saved designs, but live feeds return no messages/events. The desktop
operator API and OBS control endpoints reject every overlay read-only token.

This is desktop gating, not a server-hosted asset licensing system. A modified local
client can bypass local controls; hosted premium assets/services would need their own
server-side entitlement checks. This release uses local rendering and assets only.

No Hub files were changed in this thread. The website thread must implement and test
the response contract against its current source before paid overlays can go live.

## Release checks

Python tests cover saved identity, scoped URLs, key rotation/deletion, atomic
validation, imports, paid expiration/denial, fake local flags, token isolation,
unpaid sample privacy and both feed gates. JavaScript syntax checks pass.
215 Python tests pass. The actual player also passes an in-memory DOM regression
check for bounded particles, duplicate snapshots, deleted messages, text escaping,
image policy and hidden-source cleanup. This does not verify browser layout.

Browser interaction, OBS visibility, long-session resource usage and Windows packaged
startup still need verification before distributing a new installer. The current
0.8.0 installer is unchanged; full release is reserved for 1.0.0.

Paid overlay flags are trusted only from the official HTTPS Hub at
`https://hub.forgeddestinygaming.com`. Custom Hub connections cannot self-grant this
feature; other connection features retain their existing behavior.
