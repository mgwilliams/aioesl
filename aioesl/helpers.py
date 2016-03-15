
def print_ev(ev):
    out = "\n\n\n"
    for k in sorted(ev.keys()):
        out += "%s: %s\n" % (k, ev[k])
    print(out)