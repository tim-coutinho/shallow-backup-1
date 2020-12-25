import os
from shlex import quote
from .utils import run_cmd, get_abs_path_subfiles, exit_if_dir_is_empty, safe_mkdir, evaluate_condition
from .printing import *
from .compatibility import *
from .config import get_config
from pathlib import Path
from shutil import copytree, copyfile, copy

# NOTE: Naming convention is like this since the CLI flags would otherwise
#       conflict with the function names.


def reinstall_dots_sb(dots_path: str, home_path: str = os.path.expanduser("~"), dry_run: bool = False, verbose: bool = False):
	"""Reinstall all dotfiles and folders by copying them from dots_path
	to a path relative to home_path, or to an absolute path."""
	exit_if_dir_is_empty(dots_path, 'dotfile')
	print_section_header("REINSTALLING DOTFILES", Fore.BLUE)

	# Get paths of ALL files that we will be reinstalling from config.
	# 	If .ssh is in the config, full paths of all dots_path/.ssh/* files
	# 	will be in dotfiles_to_reinstall
	config = get_config()["dotfiles"]

	dotfiles_to_reinstall = []
	for dotfile_path_from_config, options in config.items():
		# Evaluate condition, if specified. Skip if the command doesn't return true.
		condition_success = evaluate_condition(condition=options["reinstall_condition"],
											   backup_or_reinstall="reinstall",
											   dotfile_path=dotfile_path_from_config)
		if not condition_success:
			continue

		real_path_dotfile = os.path.join(dots_path, dotfile_path_from_config)
		if os.path.isfile(real_path_dotfile):
			dotfiles_to_reinstall.append(real_path_dotfile)
		else:
			subfiles_to_add = get_abs_path_subfiles(real_path_dotfile)
			dotfiles_to_reinstall.extend(subfiles_to_add)

	# Create list of tuples containing source and dest paths for dotfile reinstallation
	# The absolute file paths prepended with ':' are converted back to valid paths
	# Format: [(source, dest), ... ]
	full_path_dotfiles_to_reinstall = []
	for source in dotfiles_to_reinstall:
		# If it's an absolute path, dest is the corrected path
		if source.startswith(":"):
			dest = "/" + source[1:]
		else:
			# Otherwise, it should go in a path relative to the home path
			dest = source.replace(dots_path, home_path + "/")
		full_path_dotfiles_to_reinstall.append((Path(source), Path(dest)))

	# Copy files from backup to system
	for dot_source, dot_dest in full_path_dotfiles_to_reinstall:
		if verbose:
			print_verbose_copy_info(dot_source, dot_dest)
		if dry_run:
			continue

		# Create dest parent dir if it doesn't exist
		safe_mkdir(dot_dest.parent)
		try:
			copy(dot_source, dot_dest)
		except PermissionError as err:
			print_red_bold(f"ERROR: {err}")
		except FileNotFoundError as err:
			print_red_bold(f"ERROR: {err}")

	print_section_header("DOTFILE REINSTALLATION COMPLETED", Fore.BLUE)


def reinstall_fonts_sb(fonts_path: str, dry_run: bool = False, verbose: bool = False):
	"""Reinstall all fonts."""
	exit_if_dir_is_empty(fonts_path, 'font')
	print_section_header("REINSTALLING FONTS", Fore.BLUE)

	# Copy every file in fonts_path to ~/Library/Fonts
	for font in get_abs_path_subfiles(fonts_path):
		fonts_dir = get_fonts_dir()
		dest_path = quote(os.path.join(fonts_dir, font.split("/")[-1]))
		if verbose:
			print_verbose_copy_info(font, dest_path)
		if dry_run:
			continue

		copyfile(quote(font), quote(dest_path))
	print_section_header("FONT REINSTALLATION COMPLETED", Fore.BLUE)


def reinstall_configs_sb(configs_path: str, dry_run: bool = False, verbose: bool = False):
	"""Reinstall all configs from the backup."""
	exit_if_dir_is_empty(configs_path, 'config')
	print_section_header("REINSTALLING CONFIG FILES", Fore.BLUE)

	config = get_config()
	for dest_path, backup_loc in config["config_mapping"].items():
		dest_path = quote(dest_path)
		source_path = quote(os.path.join(configs_path, backup_loc))

		if verbose:
			print_verbose_copy_info(source_path, dest_path)
		if dry_run:
			continue

		if os.path.isdir(source_path):
			copytree(source_path, dest_path)
		elif os.path.isfile(source_path):
			copyfile(source_path, dest_path)

	print_section_header("CONFIG REINSTALLATION COMPLETED", Fore.BLUE)


def reinstall_packages_sb(packages_path: str, dry_run: bool = False, verbose: bool = False):
	"""Reinstall all packages from the files in backup/installs."""
	def run_cmd_if_no_dry_run(command) -> int:
		if verbose:
			print_yellow_bold(f"$ {command}")
		# Return 0 for any processes depending on chained successful commands
		return 0 if dry_run else run_cmd(command)

	exit_if_dir_is_empty(packages_path, 'package')
	print_section_header("REINSTALLING PACKAGES", Fore.BLUE)

	# Figure out which install lists they have saved
	# package_mgrs = set()
	# for file in os.listdir(packages_path):
	# 	manager = file.rstrip("_list.txt")
	# 	if manager in ("gem", "cargo", "npm", "pip", "pip3", "brew", "vscode", "apm", "macports"):
	# 		package_mgrs.add(file.split("_")[0])
	package_mgrs = {
		manager.rstrip("_list.txt")
		for file in os.listdir(packages_path)
		if manager.rstrip("_list.txt") in ("gem", "cargo", "npm", "pip", "pip3", "brew", "vscode", "apm", "macports")
	}

	print_blue_bold("Package Manager Backups Found:")
	for mgr in package_mgrs:
		print_yellow("\t{}".format(mgr))
	print()

	# TODO: Multithreading for reinstallation.
	# Construct reinstallation commands and execute them
	for pm in package_mgrs:
		if pm in ["brew", "brew-cask"]:
			pm_formatted = pm.replace("-", " ")
			print_pkg_mgr_reinstall(pm_formatted)
			cmd = f"xargs {pm.replace('-', ' ')} install < {packages_path}/{pm_formatted}_list.txt"
			run_cmd_if_no_dry_run(cmd)
		elif pm == "npm":
			print_pkg_mgr_reinstall(pm)
			cmd = f"cat {packages_path}/npm_list.txt | xargs npm install -g"
			run_cmd_if_no_dry_run(cmd)
		elif pm == "pip":
			print_pkg_mgr_reinstall(pm)
			cmd = f"pip install -r {packages_path}/pip_list.txt"
			run_cmd_if_no_dry_run(cmd)
		elif pm == "pip3":
			print_pkg_mgr_reinstall(pm)
			cmd = f"pip3 install -r {packages_path}/pip3_list.txt"
			run_cmd_if_no_dry_run(cmd)
		elif pm == "vscode":
			print_pkg_mgr_reinstall(pm)
			with open(f"{packages_path}/vscode_list.txt", "r") as file:
				for package in file:
					cmd = f"code --install-extension {package}"
					run_cmd_if_no_dry_run(cmd)
		elif pm == "apm":
			print_pkg_mgr_reinstall(pm)
			cmd = f"apm install --packages-file {packages_path}/apm_list.txt"
			run_cmd_if_no_dry_run(cmd)
		elif pm == "macports":
			print_red_bold("WARNING: Macports reinstallation is not supported.")
		elif pm == "gem":
			print_red_bold("WARNING: Gem reinstallation is not supported.")
		elif pm == "cargo":
			print_red_bold("WARNING: Cargo reinstallation is not possible at the moment.\
						   \n -> https://github.com/rust-lang/cargo/issues/5593")

	print_section_header("PACKAGE REINSTALLATION COMPLETED", Fore.BLUE)


def reinstall_all_sb(dotfiles_path: str, packages_path: str, fonts_path: str, configs_path: str, dry_run: bool = False, verbose: bool = False):
	"""Call all reinstallation methods."""
	reinstall_dots_sb(dotfiles_path, dry_run=dry_run, verbose=verbose)
	reinstall_packages_sb(packages_path, dry_run=dry_run, verbose=verbose)
	reinstall_fonts_sb(fonts_path, dry_run=dry_run, verbose=verbose)
	reinstall_configs_sb(configs_path, dry_run=dry_run, verbose=verbose)
