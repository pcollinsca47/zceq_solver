from cffi import FFI
import os.path
import inspect

ffi = None
library = None

library_header = """
typedef struct {
  char data[1344];
} Solution;

typedef struct {
  unsigned int data[512];
} ExpandedSolution;

typedef struct HeaderAndNonce {
  char data[140];
} HeaderAndNonce;

typedef struct ZcEquihashSolverT ZcEquihashSolver;

ZcEquihashSolver* CreateSolver(void);

void DestroySolver(ZcEquihashSolver* solver);

int FindSolutions(ZcEquihashSolver* solver, HeaderAndNonce* inputs,
                  Solution solutions[], int max_solutions);

int ValidateSolution(ZcEquihashSolver* solver, HeaderAndNonce* inputs, Solution* solutions);

void RunBenchmark(long long nonce_start, int iterations);

bool ExpandedToMinimal(Solution* minimal, ExpandedSolution* expanded);

bool MinimalToExpanded(ExpandedSolution* expanded, Solution* minimal);

"""

def load_library(path=None):
    global library, ffi
    assert library is None

    ffi = FFI()
    ffi.cdef(library_header)

    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'libzceq_solver_sh.so')
    library = ffi.dlopen(path)
    assert library is not None


class Solver:
    def __init__(self):
        self.solver_ = self.header_ = self.solutions_ = self.solution_to_check_ = None
        self._ensure_library()
        assert library and ffi
        self.solver_ = library.CreateSolver()
        self.header_ = ffi.new("HeaderAndNonce*")
        self.solutions_ = ffi.new("Solution[16]")
        self.minimal_tmp_ = ffi.new("Solution*")
        self.expanded_tmp_ = ffi.new("ExpandedSolution*")

    def __del__(self):
        # Free the underlying resources on destruction
        library.DestroySolver(self.solver_);
        self.solver_ = None
        # cffi's cdata are collected automatically
        self.header_ = self.solutions_ = self.minimal_tmp_ = self.expanded_tmp_ = None

    def _ensure_library(self):
        # Try to load library from standard
        if (library is None):
            load_library()

    def run_benchmark(self, iterations=10, nonce_start=0):
        library.RunBenchmark(nonce_start, iterations)

    def find_solutions(self, block_header):
        assert len(block_header) == 140
        self.header_.data = block_header
        return library.FindSolutions(self.solver_, self.header_, self.solutions_, 16);

    def get_solution(self, num):
        assert(num >= 0 and num < 16)
        return bytes(ffi.buffer(self.solutions_[num].data))

    def validate_solution(self, block_header, solution):
        assert len(block_header) == 140
        assert len(solution) == 1344
        self.header_.data = block_header
        self.minimal_tmp_.data = solution
        return library.ValidateSolution(self.solver_, self.header_, self.minimal_tmp_);

    def list_to_minimal(self, solution):
        assert isinstance(solution, (list, tuple))
        assert len(solution) == 512

        # Convert a list/tuple to an ExpandedSolution instance
        data = self.expanded_tmp_.data
        for i, idx in enumerate(solution):
            data[i] = idx
        # Convert expanded to minimal
        res = library.ExpandedToMinimal(self.minimal_tmp_, self.expanded_tmp_)
        assert res
        # Return the relevant bytes
        return bytes(ffi.buffer(self.minimal_tmp_))

    def minimal_to_list(self, minimal):
        assert len(minimal) == 1344
        # Convert bytes into a minimal solution
        self.minimal_tmp_.data = minimal
        # Convert minimal to expanded solution
        res = library.MinimalToExpanded(self.expanded_tmp_, self.minimal_tmp_)
        assert res
        # Convert expanded solution to a result python list
        data = self.expanded_tmp_.data
        result = [data[i] for i in range(512)]
        return result


__all__ = ['Solver', 'load_library']
