import cProfile
try:
    import gevent
except:
    pass
import json
import pstats
import resource
import StringIO
import sys


class Profiling(object):

    def __init__(
        self,
        out_file_path=None,
        sortby='cumulative',
        num_rows=50,
        time_func=None,
    ):
        self.prof = None
        self.sortby = sortby
        self.out_file_path = out_file_path
        self.num_rows = num_rows
        self.time_func = time_func

    def __enter__(self):
        if self.time_func:
            self.prof = cProfile.Profile(self.time_func)
        else:
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
            print("Wrote to %s" % self.out_file_path)
        else:
            print(s.getvalue())


def get_cpu_usage():
    utime = resource.getrusage(resource.RUSAGE_SELF).ru_utime
    stime = resource.getrusage(resource.RUSAGE_SELF).ru_stime
    return utime + stime


class CPUTimer(object):

    def __enter__(self):
        self.start_cpu = get_cpu_usage()

    def __exit__(self, type, value, traceback):
        used = get_cpu_usage() - self.start_cpu
        print("CPU Usage: %.4f secs" % used)


class Node(json.JSONEncoder):
    def __init__(self, func, file_loc, starting_cpu):
        self.func = func
        self.file_loc = file_loc
        self.starting_cpu = starting_cpu
        self.ending_cpu = None
        self.dur = None
        self.children = []

    def end(self, ending_cpu):
        self.dur = ending_cpu - self.starting_cpu
        self.ending_cpu = ending_cpu

    def add(self, node):
        assert isinstance(node, Node)
        assert self.dur is None  # frame should not have ended
        self.children.append(node)

    def to_dict(self):
        children = []
        for child in self.children:
            children.append(child.to_dict())
        name = '/'.join(self.file_loc.split('/')[-3:]) if self.file_loc else ''
        name = "%s %s" % (self.func, name)
        return {
            'func': self.func,
            'file_loc': self.file_loc,
            'name': name,
            'value': round(self.dur, 5) if self.dur else None,
            'starting_cpu': self.starting_cpu,
            'ending_cpu': self.ending_cpu,
            'dur': self.dur,
            'children': children
        }

    def adjust(self, overhead):
        # Adjust `.dur` by removing the specified overhead for each
        # descendant node.

        if self.dur is not None:
            self.dur = self.dur - (overhead * self.len())
        for c in self.children:
            c.adjust(overhead)

    def len(self):
        c = len(self.children)
        return c + sum([child.len() for child in self.children])

    @classmethod
    def from_frame(cls, frame):
        return cls(
            func=frame[1],
            file_loc=frame[3],
            starting_cpu=frame[2]
        )

class Profiler(object):
    def __init__(self, outfile_path=None, greenlet=None):
        self.ref = None
        self.root = None
        self.outfile_path = outfile_path
        self.original_profiler = sys.getprofile()
        self.frames = []
        self.greenlet_id = id(greenlet) if greenlet else None
        self.overhead = None  # set in calibrate()

    def profiler(self, frame, event, arg):
        if self.greenlet_id and id(gevent.getcurrent()) != self.greenlet_id:
            return
        if event != 'call' and event != 'return':
            return
        self.frames.append((
            event,
            frame.f_code.co_name,
            get_cpu_usage(),
            "%s:%s" % (frame.f_code.co_filename, frame.f_lineno),
        ))

    def calibrate(self, n=10000, reset=True):
        func = lambda: None

        # Try to measure overhead calibration code
        start = get_cpu_usage()
        for i in range(n):
            func()
        end = get_cpu_usage()
        calibration_overhead = end - start

        # Measure over head of profiling + calibration
        original_profiler = sys.getprofile()
        sys.setprofile(self.profiler)
        start = get_cpu_usage()
        for i in range(n):
            func()
        end = get_cpu_usage()
        sys.setprofile(original_profiler)

        # Overhead is total - calibration... in theory.
        total_overhead = end - start
        self.overhead = (total_overhead - calibration_overhead) / float(n)

        if reset:
            self.frames = []
        return self.overhead

    def build_tree(self):
        self.root = Node('root', None, get_cpu_usage())
        stack = []

        for i, frame in enumerate(self.frames):
            event = frame[0]
            if event == 'call':
                parent = stack[-1] if stack else self.root
                node = Node.from_frame(frame)
                parent.add(node)
                stack.append(node)
            elif event == 'return':
                if not stack:  # no matching 'call' event logged
                    continue
                node = stack.pop()
                if node.func != frame[1]:
                    import pdb
                    pdb.set_trace()
                assert node.func == frame[1]
                node.end(frame[2])

        self.root.dur = sum(
            [c.dur for c in self.root.children if c.dur is not None]
        )

        if self.overhead is not None:
            self.root.adjust(self.overhead)

        return self.root

    def start(self):
        sys.setprofile(self.profiler)

    def end(self):
        sys.setprofile(self.original_profiler)
        end = get_cpu_usage()
        root = self.build_tree()
        self.root.end(end)
        if self.outfile_path:
            fp = open(self.outfile_path, 'w')
            fp.write(json.dumps(root.to_dict()))
            fp.close()

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

    print("Base-line (DRF):")
    with CPUTimer():
        do_thing(szr, user)

    szr.enable_optimization = True
    print("DREST latest:")
    with CPUTimer():
        do_thing(szr, user)

    szr.enable_optimization = True
    szr.getattr_optimization = True
    print("With getattr optimization:")
    with CPUTimer():
        do_thing(szr, user)

    with Profiling():
        do_thing(szr, user)
