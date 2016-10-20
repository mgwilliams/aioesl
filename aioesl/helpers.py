from lxml import etree
from .log import aioesl_log
import json


def print_event(event, filter=None, print_func=None):
    if event is None or event == {}:
        return

    if print_func is None:
        outer = print
    else:
        outer = print_func

    for k in sorted(event.keys()):
        if filter is None:
            outer("%s: %s" % (k, event[k]))
        else:
            if str(filter) in str(k) or str(filter) in str(event[k]):
                outer("%s: %s" % (k, event[k]))


def parse_text(split="|", raw="", need_fields=[], rm_first_lines=1, rm_last_lines=1, field_name_line=0, logger=aioesl_log):
    """

    :param split:
    :param raw:
    :param need_fields:
    :param rm_first_lines: remove X first lines
    :param rm_last_lines: remove X last lines
    :param field_name_line: field line num
    :param logger:
    :return:
    """
    data = []
    try:
        raw = raw.get("DataResponse")
        if raw is None:
            return data
    except Exception as error:
        logger.exception(error)
        return None

    lines = raw.splitlines()
    keys = []
    if len(lines) > 1:
        keys = lines[field_name_line].strip().split(split)

    if rm_first_lines > 0 and len(lines) > 1:
        lines = lines[rm_first_lines:]

    if rm_last_lines > 0 and len(lines) > 1:
        lines = lines[:rm_last_lines]

    if len(lines) > 0 and len(keys) > 0:
        for line in lines:
            if split not in line:
                continue
            fields = line.split(split)
            if len(fields) != len(keys):
                continue
            r = {keys[i].strip(): fields[i].strip() for i in range(0, len(keys)) if keys[i] in need_fields or len(need_fields) == 0}
            data.append(r)

    # print("keys-> ", keys, "\n", "lines-> ", lines, "\n", "data-> ", data)
    return data


def parse_xml(raw, logger=aioesl_log):
    in_str_xml = raw.get("DataResponse")
    if in_str_xml is None:
        return None

    try:
        xml = etree.fromstring(in_str_xml)
        return xml
    except Exception as error:
        logger.exception(error)
        return None


def parse_json(raw, logger=aioesl_log):
    try:
        if not isinstance(raw, dict):
            return None

        res = raw.get("DataResponse")

        if res is None:
            return None

        res = json.loads(res, encoding='utf-8').get("rows")
        if not isinstance(res, list):
            return None

        return res

    except Exception as error:
        logger.exception(error)
        return None


def parse_raw_split(split="|", raw={}, need_fields=[], kill_fl=False):
    data = []
    try:
        raw = raw.get("DataResponse")
        if raw is None:
            return data
    except:
        aioesl_log.exception(msg="parse_raw_split")
        return data

    lines = raw.splitlines()
    if kill_fl and len(lines) > 1:
        lines = lines[1:]

    if len(lines) > 1:
        keys = lines[0].strip().split(split)
        for line in lines[1:]:
            fields = line.split(split)
            if len(fields) != len(keys):
                continue
            r = {keys[i]: fields[i] for i in range(0, len(keys)) if keys[i] in need_fields or len(need_fields) == 0}
            data.append(r)

    return data


def json_response_check(data=None):

    if data.get("DataResponse") is None:
        return False, data.get("ErrorData")

    try:
        data = json.loads(data["DataResponse"])
    except:
        print(data, type(data))
        return False, "No Json Data"

    if data.get("status") != "success":
        return False, data.get("status")

    return True, data.get("response", [])


def json_ccfilter(data=list(), need_field=None, filter_field=None, filter_value=None):
    result = []
    for row in data:
        append = False
        if filter_field is None:
            append = True
        elif row[filter_field].endswith(str(filter_value)):
            append = True

        if append:
            if isinstance(need_field, str):
                result.append(row[need_field])
            elif isinstance(need_field, list):
                r = {i: row[i] for i in need_field if i in row.keys()}
                result.append(r)
            else:
                result.append(row)
    return result
