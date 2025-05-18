{ pkgs, devEnv, configFile, isPrivate ? true }:

(pkgs.python312Packages.buildPythonApplication rec {
  pname = "cli";
  version = "0.2.0";
  versionBuild = "0.2.0";

  pyproject = true;

  src = ./.;

  dontUseCmakeConfigure = true;

  build-system = with pkgs.python312Packages; [
    setuptools
  ];

  dependencies =
    let
      packages = with pkgs; [
        git
        openssh
      ] ++ pkgs.lib.optionals (isPrivate) [
        rsync
      ];
      pythonPackages =
        with pkgs.python312Packages; [
          click
          gitpython
          pytimeparse
          pyyaml
          rich
          rich-click
        ] ++ pkgs.lib.optionals (isPrivate) [
          requests
          urllib3
          python-gitlab
          tqdm
        ];
    in
    packages ++ pythonPackages;

  makeWrapperArgs = [
    "--set SYSTEM ${pkgs.system}"
    "--set VERSION ${version}"
    "--set VERSION_BUILD ${versionBuild}"
    "--set CONFIG_PATH ${configFile}"
  ] ++ pkgs.lib.optionals (isPrivate) [
    "--set PRIVATE 1"
  ];
}).overrideAttrs (finalAttrs: previousAttrs:
let
  allowedUserEnv = pkgs.lib.concatStringsSep "|" [
    "SSH"
    "USER"
    "TERM"
    ".*SSL.*"
    "_CLI_VERSION"
    "TESTER_TOKEN"
    "GITLAB_API_TOKEN"
    "CI_PROJECT_NAME"
    "CI_PIPELINE_CREATED_AT"
  ];
in
{
  # Don't pass any user environment variables except SSL-specific.
  postFixup = with pkgs; previousAttrs.postFixup
    + "sed -i '1 r ${devEnv}' $out/bin/cli\n"
    + "sed -i '2i unset $(${coreutils}/bin/env | ${gnugrep}/bin/grep -vE \"${allowedUserEnv}\" | ${coreutils}/bin/cut -d= -f1)' $out/bin/cli\n";
})
