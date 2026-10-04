# Explicit offline authorization while the owner is away

An owner may explicitly authorize finite `frame_bank_pc` work while away. The
PC lease records `owner_present=false` and `owner_authorized_while_away=true`,
plus the exact current authorization as evidence. Absence without that explicit
flag remains refused. This cannot authorize headset, network, VR, installation,
settings or arm-file work; the only permitted operation remains `frame_bank_pc`.

Use `supervised.session(..., owner_present=False,
owner_authorized_while_away=True)` or the CLI's `--owner-authorized-while-away`.
The existing two-hour maximum, independent GPU monitor, compute-backend and
VRAM/device safety checks, stop marker, job ownership, parent-death cancellation
and final cleanup all apply. This adds truthful attestation to the existing
PC-only mechanism; it does not change any safety stop or the unattended headset
authorization mechanism. No arm file is read or modified.
