{ nixpkgs, flake-utils }:
with flake-utils.lib; eachSystem [ system.x86_64-linux system.x86_64-darwin ]
  (system:
  let
    pkgs = nixpkgs.legacyPackages.${system};
    devEnv = (import ../../devEnv/cpp.nix { inherit pkgs; });
  in
  {
    packages = {
      cli_pcp = (import ../../cli {
        inherit pkgs devEnv;
        configFile = ./config.yml;
        isPrivate = false;
      });

      cli_pcp_private = (import ../../cli {
        inherit pkgs devEnv;
        configFile = ./config.yml;
        isPrivate = true;
      });
    };
  })
