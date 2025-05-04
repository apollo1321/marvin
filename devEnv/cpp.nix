{ pkgs, extraPackages ? [ ] }:
let
  llvmPackages = pkgs.llvmPackages_20;

  envVars = ''
    export ASAN_SYMBOLIZER_PATH=${llvmPackages.libllvm}/bin/llvm-symbolizer
    export TSAN_SYMBOLIZER_PATH=${llvmPackages.libllvm}/bin/llvm-symbolizer
    export ASAN_OPTIONS="detect_leaks=1"
    export CFLAGS="-isystem ${llvmPackages.compiler-rt-libc.dev}/include"
    export CXXFLAGS="-isystem ${llvmPackages.compiler-rt-libc.dev}/include"
  '';

  util = import ./util.nix { inherit pkgs; };
in

llvmPackages.stdenv.mkDerivation {
  pname = "cli-env-cpp";
  version = "0.2.0";

  buildPhase = ''
    export | grep -vE  "${util.unallowedDevEnv}" >> $out
    echo '${envVars}' >> $out
  '';

  phases = [ "buildPhase" ];

  buildInputs = with pkgs; [
    cmake
    llvmPackages.bintools # Utilities for backtrace symbolization.
    llvmPackages.clang-tools
    ninja
    which
    gtest
  ] ++ lib.optionals (stdenv.isLinux) [
    bubblewrap # Utility to run tests in an isolated environment.
  ] ++ lib.optionals (stdenv.isDarwin) [
    cctools # Needed for install_name_tool.
    llvmPackages.libllvm # Needed for dsymutil.
  ] ++ extraPackages;
}
