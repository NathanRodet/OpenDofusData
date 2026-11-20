//! Tells the linker where to find `wpcap.lib` (made by `scripts/make-wpcap-lib.ps1`, or the Npcap SDK).

use std::env;
use std::path::PathBuf;

fn main() {
    println!("cargo:rerun-if-env-changed=NPCAP_LIB_DIR");
    println!("cargo:rerun-if-changed=npcap-lib");
    let default = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap_or_default()).join("npcap-lib");
    let directory = env::var("NPCAP_LIB_DIR").map(PathBuf::from).unwrap_or(default);
    if directory.join("wpcap.lib").exists() {
        println!("cargo:rustc-link-search=native={}", directory.display());
    }
}
