from lxml import etree
from .log import aioesl_log


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


def parse_raw_split(split="|", raw="", need_fields=[], kill_fl=False, logger=aioesl_log):
    data = []
    try:
        raw = raw.get("DataResponse")
        if raw is None:
            return data
    except Exception as error:
        logger.exception(error)
        return None

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


def parse_raw_xml(raw, logger=aioesl_log):
    in_str_xml = raw.get("DataResponse")
    if in_str_xml is None:
        return None

    try:
        xml = etree.fromstring(in_str_xml)
        return xml
    except Exception as error:
        logger.exception(error)
        return None
