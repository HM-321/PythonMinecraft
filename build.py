import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
DIST_DIR = ROOT_DIR / "dist"

SPEC_FILES = {
    "Darwin": {
        "client": "MinecraftBuild.spec",
        "debug": "MinecraftBuildDebug.spec",
        "server": "MinecraftBuildServer.spec",
    },
    "Windows": {
        "client": "MinecraftBuildWindows.spec",
        "server": "MinecraftBuildServer.spec",
    },
}

OUTPUT_NAMES = {
    "client": "MinecraftBuild",
    "debug": "MinecraftBuildDebug",
    "server": "MinecraftBuildServer",
}


def get_spec_path(system: str, mode: str) -> Path:
    os_specs = SPEC_FILES.get(system)

    if os_specs is None:
        raise RuntimeError(f"未対応のOS: {system}")

    spec_name = os_specs.get(mode)

    if spec_name is None:
        raise RuntimeError(
            f"{system}では'{mode}'ビルドに対応していない"
        )

    spec_path = ROOT_DIR / spec_name

    if not spec_path.is_file():
        raise FileNotFoundError(
            f"specファイルが見つからない: {spec_path}"
        )

    return spec_path


def remove_directory(directory_name: str) -> None:
    directory = ROOT_DIR / directory_name

    if directory.exists():
        print(f"削除: {directory}")
        shutil.rmtree(directory)


def clean_all_outputs() -> None:
    remove_directory("build")
    remove_directory("dist")


def organize_macos_app(mode: str) -> None:
    output_name = OUTPUT_NAMES[mode]

    app_path = DIST_DIR / f"{output_name}.app"
    output_directory = DIST_DIR / output_name
    destination = output_directory / f"{output_name}.app"

    if not app_path.exists():
        print(f"警告: appが見つからない: {app_path}")
        return

    output_directory.mkdir(parents=True, exist_ok=True)

    if destination.exists():
        shutil.rmtree(destination)

    shutil.move(str(app_path), str(destination))

    print(f"appを移動: {destination}")


def run_build(
    spec_path: Path,
    mode: str,
    system: str,
) -> None:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        str(spec_path),
    ]

    print()
    print("=" * 60)
    print(f"ビルド種別: {mode}")
    print(f"spec: {spec_path.name}")
    print("=" * 60)

    subprocess.run(
        command,
        cwd=ROOT_DIR,
        check=True,
    )

    if system == "Darwin":
        organize_macos_app(mode)

    print(f"完了: {mode}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="現在のOSに合わせてMinecraftBuildを生成する"
    )

    parser.add_argument(
        "--mode",
        choices=("all", "client", "server", "debug"),
        default="all",
        help=(
            "ビルド種別。"
            "既定値のallではクライアントとサーバーを両方ビルドする"
        ),
    )

    parser.add_argument(
        "--clean-all",
        action="store_true",
        help="ビルド前にbuildとdistを完全に削除する",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    system = platform.system()
    architecture = platform.machine()

    print(f"OS: {system}")
    print(f"CPU: {architecture}")
    print(f"プロジェクト: {ROOT_DIR}")

    if args.mode == "all":
        modes = ["client", "server"]
    else:
        modes = [args.mode]

    try:
        spec_paths = [
            (mode, get_spec_path(system, mode))
            for mode in modes
        ]

        if args.clean_all:
            clean_all_outputs()

        for mode, spec_path in spec_paths:
            run_build(
                spec_path=spec_path,
                mode=mode,
                system=system,
            )

    except (FileNotFoundError, RuntimeError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        sys.exit(1)

    except subprocess.CalledProcessError as error:
        print(
            f"ビルドに失敗した。終了コード: {error.returncode}",
            file=sys.stderr,
        )
        sys.exit(error.returncode)

    print()
    print("=" * 60)
    print("すべてのビルドが完了した")
    print(f"出力先: {DIST_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()