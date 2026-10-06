// CI-only host harness: compile the production modules without Android/VR dependencies.
// fetch_sources.sh reconstructs these paths under the workflow's XRWIRED_INPUTS=ws.
extern crate self as alvr_packets;

#[path = "../ws/research/ALVR-20.13.0/alvr/packets/src/dual_stream.rs"]
pub mod dual_stream;

#[path = "../ws/research/ALVR-20.13.0/alvr/client_core/src/stereo_pairing.rs"]
pub mod stereo_pairing;
