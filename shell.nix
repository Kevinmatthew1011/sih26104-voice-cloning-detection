{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  name = "voice-guard-env";

  buildInputs = with pkgs; [
    python311
    python311Packages.pip
    python311Packages.virtualenv
    libsndfile
    ffmpeg
    zlib
    stdenv.cc.cc.lib
  ];

  shellHook = ''
    export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath [
      pkgs.stdenv.cc.cc.lib
      pkgs.zlib
      pkgs.libsndfile
      pkgs.ffmpeg
    ]}:$LD_LIBRARY_PATH"
  '';
}
