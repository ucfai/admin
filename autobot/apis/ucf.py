from collections import OrderedDict
from datetime import datetime
from typing import Dict, List

import pandas as pd
import requests

from autobot.concepts import Group, MeetingMeta, Semester

# it's unlikely this URL will change, but should be occassionally checked
CALENDAR_URL = "https://calendar.ucf.edu"
# these holidays need to match, specifically, how UCF labels them
OBS_HOLIDAYS = {
    "spring": ["Spring Break", "Martin Luther King Jr. Day"],
    "summer": [],
    "fall": ["Veterans Day", "Labor Day", "Thanksgiving"],
}

# NOTE make sure to consider 0-indexing here
SEMESTER_LEN = {"spring": 14, "summer": 10, "fall": 15}


def day2index(s: str) -> int:
    weekdays = "Mon Tue Wed Thu Fri Sat Sun".lower().split()
    return weekdays.index(s.lower())


def make_schedule(group: Group, schedule: Dict):
    date_range, holidays = parse_calendar(group)
    assert all([v for v in schedule.values()])

    wday, room = schedule["wday"], schedule["room"]
    offset = schedule["start_offset"]

    # generate meeting dates, on a weekly basis
    meeting_dates = pd.Series(date_range)
    meeting_start = offset * 7 + day2index(wday)

    # TODO: support non-standard dates for groups, e.g. like "Supplementary"
    meeting_dates = meeting_dates[meeting_start::7]
    if holidays is not None:
        # remove holidays
        meeting_dates = meeting_dates[~meeting_dates.isin(holidays)]

    time_s, time_e = schedule["time"].split("-")
    meeting_time = pd.Timedelta(hours=int(time_s[:2]), minutes=int(time_s[2:]))
    meeting_dates += meeting_time

    # logging.info(f"Meeting dates\n{meeting_dates}")

    schedule = [MeetingMeta(pd.to_datetime(mtg), room) for mtg in meeting_dates]
    # logging.debug(schedule)

    return schedule


def parse_calendar(group: Group) -> tuple:
    holidays = OBS_HOLIDAYS[group.semester.name]
    calendar_url = f"{CALENDAR_URL}/json/{group.semester.year}/{group.semester.name}"

    ucf_parsed = requests.get(calendar_url).json()["terms"][0]["events"]
    df_calendar = pd.DataFrame.from_dict(ucf_parsed)

    summary_mask = df_calendar["summary"]
    starts = df_calendar.loc[summary_mask.str.contains("Classes Begin")].iloc[0]
    ends = df_calendar.loc[summary_mask.str.contains("Classes End")].iloc[0]

    # generate a DataFrame with all possible dates (to act like a calendar)
    date_range = pd.Series(
        pd.date_range(start=starts["dtstart"][:-1], end=ends["dtstart"][:-1])
    )

    holidays = []
    for holiday in OBS_HOLIDAYS[group.semester.name]:
        day2remove = df_calendar.loc[summary_mask.str.contains(holiday)].iloc[0]
        beg = day2remove["dtstart"][:-1]
        end = day2remove["dtend"][:-1] if day2remove["dtend"] else beg
        holidays.append(pd.Series(pd.date_range(start=beg, end=end)))

    if holidays is not None:
        holidays = pd.concat(holidays)

    return date_range, holidays


def determine_semester() -> Semester:
    """A method which determines the current semester based on the present date
    and uses the UCF calendar redirect to inform it's decision.
    """
    current_url = requests.get(CALENDAR_URL).url
    current_date = datetime.now()

    may, aug, dec = [5, 8, 12]  # May, Aug, Dec (1-indexed)

    semester_dict = OrderedDict({"spring": may, "summer": aug, "fall": dec})

    semester_list = list(semester_dict.keys())
    n_semesters = len(semester_list)

    for idx, (semester, month) in enumerate(semester_dict.items()):
        if current_url.endswith(semester) and current_date.month == month:
            next_semester = semester_list[(idx + 1) % n_semesters]
            current_url = current_url.replace(semester, next_semester)

            if semester == "fall":  # increment the year as well
                year = current_date.year
                current_url = current_url.replace(f"{year}", f"{year + 1}")

    year, name = current_url.replace(f"{CALENDAR_URL}/", "").split("/")

    return Semester(name=name, year=year)
