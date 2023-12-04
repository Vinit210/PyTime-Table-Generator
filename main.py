from optapy import solver_factory_create
from optapy.types import SolverConfig, Duration
from constraints import define_constraints
from domain import TimeTable, Lesson, generate_problem

solver_config = SolverConfig().withEntityClasses(Lesson) \
    .withSolutionClass(TimeTable) \
    .withConstraintProviderClass(define_constraints) \
    .withTerminationSpentLimit(Duration.ofSeconds(30))

solver = solver_factory_create(solver_config).buildSolver()
solution = solver.solve(generate_problem())
from optapy import solver_factory_create

solution = solver_factory_create(solver_config)\
    .buildSolver()\
    .solve(generate_problem())
print(solution)