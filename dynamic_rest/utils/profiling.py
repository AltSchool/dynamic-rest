import cProfile
import pstats
import resource
import StringIO


class Profiling(object):

    def __init__(
        self,
        out_file_path=None,
        sortby='cumulative',
        num_rows=50
    ):
        self.prof = None
        self.sortby = sortby
        self.out_file_path = out_file_path
        self.num_rows = num_rows

    def __enter__(self):
        self.prof = cProfile.Profile()
        self.prof.enable()

    def __exit__(self, type, value, traceback):
        self.prof.disable()
        s = StringIO.StringIO()
        ps = pstats.Stats(self.prof, stream=s).sort_stats(self.sortby)
        ps.print_stats(self.num_rows)

        if self.out_file_path:
            fp = open(self.out_file_path, 'w')
            fp.write(s.getvalue())
            fp.close()
            print "Wrote to %s" % self.out_file_path
        else:
            print s.getvalue()


def get_cpu_usage():
    utime = resource.getrusage(resource.RUSAGE_SELF).ru_utime
    stime = resource.getrusage(resource.RUSAGE_SELF).ru_stime
    return utime + stime


class CPUTimer(object):

    def __enter__(self):
        self.start_cpu = get_cpu_usage()

    def __exit__(self, type, value, traceback):
        used = get_cpu_usage() - self.start_cpu
        print "CPU Usage: %.4f secs" % used


def run_test():
    from tests.serializers import UserSerializer
    from tests.models import User

    def do_thing(szr, user):
        for i in range(1000):
            szr.to_representation(user)

    user = user = User.objects.prefetch_related(
        'groups', 'profile', 'location__cat_set', 'permissions'
    ).first()

    szr = UserSerializer(include_fields='*')
    szr.enable_optimization = False
    szr.getattr_optimization = False

    print "Base-line (DRF):"
    with CPUTimer():
        do_thing(szr, user)

    szr.enable_optimization = True
    print "DREST latest:"
    with CPUTimer():
        do_thing(szr, user)

    szr.enable_optimization = True
    szr.getattr_optimization = True
    print "With getattr optimization:"
    with CPUTimer():
        do_thing(szr, user)

    with Profiling():
        do_thing(szr, user)
