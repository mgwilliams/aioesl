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