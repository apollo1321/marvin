{
  description = "Marvin - reproducible clients for educational courses";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    with flake-utils.lib; eachSystem [ system.x86_64-linux system.x86_64-darwin ] (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        llvmPackages = pkgs.llvmPackages_20;

        # The list of packages is available here: https://search.nixos.org/packages
        devPackages = with pkgs; [
          cmake
          git
          llvmPackages.bintools # Utilities for backtrace symbolization.
          llvmPackages.clang-tools
          ninja
          which
          # Place your packages here if you need any.
          # PRIVATE BEGIN
          rsync
          gtest
          # PRIVATE END
        ] ++ lib.optionals (stdenv.isLinux) [
          bubblewrap # Utility to run tests in an isolated environment.
        ] ++ lib.optionals (stdenv.isDarwin) [
          cctools # Needed for install_name_tool.
          llvmPackages.libllvm # Needed for dsymutil.
        ] ++ lib.optionals (builtins.pathExists ./extra_pkgs.nix)
          (import ./extra_pkgs.nix { inherit pkgs; });

        cliPackages = with pkgs.python312Packages; [
          click
          pyyaml
          termcolor
          pytimeparse
          # PRIVATE BEGIN
          requests
          urllib3
          python-gitlab
          tqdm
          # PRIVATE END
        ];

        allowedUserEnv = pkgs.lib.concatStringsSep "|" [
          ".*SSL.*"
          # PRIVATE BEGIN
          "TESTER_TOKEN"
          "GITLAB_API_TOKEN"
          "CI_PROJECT_NAME"
          "CI_PIPELINE_CREATED_AT"
          # PRIVATE END
        ];

        unallowedDevEnv = pkgs.lib.concatStringsSep "|" [
          ".*SSL.*"
          ".*TEMP.*"
          ".*TMP.*"
          "PWD"
          "OLDPWD"
          "system"
          "out"
          "outputs"
          "pname"
          "NIX_ENFORCE_PURITY"
        ];

        version = builtins.readFile ./.version;
        versionBuild = "0.2.0";

        envVars = ''
          export SYSTEM=${system}
          export VERSION=${version}
          export VERSION_BUILD=${versionBuild}
          export CONFIG_PATH=${./config.yml}
          export ASAN_SYMBOLIZER_PATH=${llvmPackages.libllvm}/bin/llvm-symbolizer
          export TSAN_SYMBOLIZER_PATH=${llvmPackages.libllvm}/bin/llvm-symbolizer
          export ASAN_OPTIONS="detect_leaks=1"
          export CFLAGS="-isystem ${llvmPackages.compiler-rt-libc.dev}/include"
          export CXXFLAGS="-isystem ${llvmPackages.compiler-rt-libc.dev}/include"
        '';

        exportedEnv = pkgs.llvmPackages_20.stdenv.mkDerivation {
          pname = "cli-env";

          inherit version;

          buildPhase = ''
            export | grep -vE  "${unallowedDevEnv}" >> $out
            echo '${envVars}' >> $out
          '';

          phases = [ "buildPhase" ];
          buildInputs = devPackages;
        };
      in
      rec {
        packages.default = packages.cli;

        packages.cli = (pkgs.python312Packages.buildPythonApplication {
          pname = "cli";
          inherit version;
          pyproject = true;

          src = ./.;

          dontUseCmakeConfigure = true;

          build-system = with pkgs.python312Packages; [
            setuptools
          ];

          dependencies = cliPackages;
        }).overrideAttrs (finalAttrs: previousAttrs: {
          # Don't pass any user environment variables except SSL-specific.
          postFixup = with pkgs; previousAttrs.postFixup
            + "sed -i '1 r ${exportedEnv}' $out/bin/cli\n"
            + "sed -i '2i unset $(${coreutils}/bin/env | ${gnugrep}/bin/grep -vE \"${allowedUserEnv}\" | ${coreutils}/bin/cut -d= -f1)' $out/bin/cli\n";
        });
      }
    );
}
