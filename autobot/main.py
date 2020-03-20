from typing import List
import logging
import os
import sys
import shutil
from argparse import ArgumentParser

from tqdm import tqdm

from autobot import ORG_NAME
from autobot.actions import meetings, paths, syllabus
from autobot.apis import ucf, kaggle
from autobot.concepts import Group, Meeting, Semester, groups
from autobot.pathing import templates, repositories


def _argparser(**kwargs):
    parser = ArgumentParser(prog="autobot")

    parser.add_argument("group", choices=groups.ACCEPTED.keys())
    parser.add_argument("semester", nargs="?", default=kwargs["semester"])

    if "IN_DOCKER" in os.environ:
        parser.add_argument("--wait", action="store_true")

    action = parser.add_subparsers(title="action", dest="action")

    setup = action.add_parser("semester-setup")
    upkeep = action.add_parser("semester-upkeep")

    which_mtgs = upkeep.add_mutually_exclusive_group(required=True)
    which_mtgs.add_argument("-d", "--date", type=str, help="date format: MM/DD")
    which_mtgs.add_argument(
        "-n", "--name", type=str, help="name format: <filename> - `from syllabus.yml`"
    )
    which_mtgs.add_argument("--all", action="store_true")

    parser.add_argument("--overwrite", action="store_true")

    return parser.parse_args()


def main():
    semester = ucf.determine_semester()

    args = _argparser(**{"semester": repr(semester)})

    if "IN_DOCKER" in os.environ and args.wait:
        foreground()

    args.semester = Semester(shortname=args.semester)

    # `groups.ACCEPTED` makes use of Python's dict-based execution to allow for
    #   restriction to one of the Groups listed in `concept/groups.py`
    group = groups.ACCEPTED[args.group](args.semester)

    if args.action == "semester-setup":
        semester_setup(group)
    elif args.action == "semester-upkeep":
        try:
            syllabus.init(group)
            print("Done generating syllabus. Exiting.")
            exit(0)
        except AssertionError as e:
            pass

        syllabus.sort(group)
        meetings = syllabus.parse(group)

        if not args.all:
            meeting = None
            if args.date:
                meeting = next((m for m in meetings if args.date in repr(m)), None)
            elif args.name:
                meeting = next((m for m in meetings if args.name in repr(m)), None)

            if meeting is None:
                raise ValueError("Couldn't find the meeting you were looking for!")

            meetings = [meeting]  # formats so semester upkeep accepts

        semester_upkeep(meetings, overwrite=args.overwrite)


def foreground():
    import time

    print("Waiting...")
    while True:
        time.sleep(1)


def semester_setup(group: Group) -> None:
    """Sets up the skeleton for a new semester.
    1. Copies base `yml` into `<group>/<semester>/`
    2. Sets up the Website's entires for the given semester. (NB: Does **not**
       make posts.)
    3. Performs a similar setup with Google Drive & Google Forms.
    4. Generates skeleton for the login/management system.
    """
    path = repositories.local_semester_root(group)
    if path.exists():
        logging.warning(f"{path} exists! Tread carefully.")
        overwrite = input(
            "The following actions **are destructive**. " "Continue? [y/N] "
        )
        if overwrite.lower() not in ["y", "yes"]:
            return

    path.mkdir()

    # region 1. Copy base `yml` files.
    #   1. env.yml
    #   2. overhead.yml
    env = templates.load("group/env.yml.j2")
    (path / "env.yml").touch()
    with open(path / "env.yml", "w") as f:
        f.write(
            env.render(
                org_name=ORG_NAME, group_name=repr(group), semester=repr(group.semester)
            )
        )

    shutil.copy(str(templates.get("group/overhead.yml")), str(path / "overhead.yml"))
    # endregion

    # region 2. Setup Website for this semester
    paths.site_group_folder(group)
    # endregion

    # region 3. Setup Google Drive & Google Forms setup
    # TODO: make Google Drive folder for this semester
    # TODO: make "Sign-Up" Google Form and Google Sheet
    # TODO: make "Sign-In" Google Form and Google Sheet
    # endregion

    # region 4. Setup YouTube Semester Playlist
    # TODO: create YouTube playlist
    # endregion


def semester_upkeep(syllabus: List[Meeting], overwrite: bool = False) -> None:
    """Assumes a [partially] complete Syllabus; this will only create new
    Syllabus entries' resources - thus avoiding potentially irreversible
    changes/deletions).

    1. Reads `overhead.yml` and parses Coordinators
    2. Reads `syllabus.yml`, parses the Semester's Syllabus, and sets up
       Notebooks.
    """
    for meeting in tqdm(syllabus, desc="Building / Updating Syllabus", file=sys.stdout):
        tqdm.write(f"{repr(meeting)} ~ {str(meeting)}")

        # Perform initial directory checks/clean-up
        meetings.update_or_create_folders_and_files(meeting)

        # Make edit in the group-specific repo
        meetings.update_or_create_notebook(meeting, overwrite=overwrite)
        meetings.download_papers(meeting)
        kaggle.push_kernel(meeting)

        # Make edits in the ucfai.org repo
        # banners.render_cover(meeting)
        # banners.render_weekly_instagram_post(meeting)  # this actually needs a more global setting
        meetings.export_notebook_as_post(meeting)

        # Video Rendering and Upload
        # videos.dispatch_recording(meeting)  # unsure that this is needed
        # banners.render_video_background(meeting)
        # this could fire off a request to GCP to avoid long-running local renders
        # videos.compile_and_render(meeting)
        # videos.upload(meeting)
