{ nixpkgs, flake-utils }:
with flake-utils.lib; eachSystem [ system.x86_64-linux system.x86_64-darwin ]
  (system:
  let
    pkgs = nixpkgs.legacyPackages.${system};
    devEnv = (import ../../devEnv/cpp.nix { inherit pkgs; });
  in
  {
    packages = {
      pcp_cli = (import ../../cli {
        inherit pkgs devEnv;
        configFile = ./config.yml;
        isPrivate = false;
      });

      pcp_cli_private = (import ../../cli {
        inherit pkgs devEnv;
        configFile = ./config.yml;
        isPrivate = true;
      });
    };
  })
