from optapy import problem_fact, planning_id
from optapy import planning_entity, planning_variable
from optapy import constraint_provider
from optapy.types import Joiners, HardSoftScore
from datetime import datetime, date, timedelta
from optapy import planning_solution, planning_entity_collection_property, \
    problem_fact_collection_property, \
    value_range_provider, planning_score
from datetime import time
from optapy import solver_manager_create
from optapy.types import SolverConfig, Duration
from ipywidgets import Tab
from ipysheet import sheet, cell, row, column, cell_range


@problem_fact
class Room:
    def __init__(self, id, name):
        self.id = id
        self.name = name

    @planning_id
    def get_id(self):
        return self.id

    def __str__(self):
        return f"Room(id={self.id}, name={self.name})"
@problem_fact
class Timeslot:
    def __init__(self, id, day_of_week, start_time, end_time):
        self.id = id
        self.day_of_week = day_of_week
        self.start_time = start_time
        self.end_time = end_time

    @planning_id
    def get_id(self):
        return self.id

    def __str__(self):
        return (
                f"Timeslot("
                f"id={self.id}, "
                f"day_of_week={self.day_of_week}, "
                f"start_time={self.start_time}, "
                f"end_time={self.end_time})"
        )


@planning_entity
class Lesson:
    def __init__(self, id, subject, teacher, student_group, timeslot=None, room=None):
        self.id = id
        self.subject = subject
        self.teacher = teacher
        self.student_group = student_group
        self.timeslot = timeslot
        self.room = room

    @planning_id
    def get_id(self):
        return self.id

    @planning_variable(Timeslot, ["timeslotRange"])
    def get_timeslot(self):
        return self.timeslot

    def set_timeslot(self, new_timeslot):
        self.timeslot = new_timeslot

    @planning_variable(Room, ["roomRange"])
    def get_room(self):
        return self.room

    def set_room(self, new_room):
        self.room = new_room

    def __str__(self):
        return (
            f"Lesson("
            f"id={self.id}, "
            f"timeslot={self.timeslot}, "
            f"room={self.room}, "
            f"teacher={self.teacher}, "
            f"subject={self.subject}, "
            f"student_group={self.student_group}"
            f")"
        )

# Trick since timedelta only works with datetime instances
today = date.today()


def within_30_minutes(lesson1, lesson2):
    between = datetime.combine(today, lesson1.timeslot.end_time) - datetime.combine(today, lesson2.timeslot.start_time)
    return timedelta(minutes=0) <= between <= timedelta(minutes=30)


@constraint_provider
def define_constraints(constraint_factory):
    return [
        # Hard constraints
        room_conflict(constraint_factory),
        teacher_conflict(constraint_factory),
        student_group_conflict(constraint_factory),
        # Soft constraints
        teacher_room_stability(constraint_factory),
        teacher_time_efficiency(constraint_factory),
        student_group_subject_variety(constraint_factory)
    ]


def room_conflict(constraint_factory):
    # A room can accommodate at most one lesson at the same time.
    return constraint_factory \
        .for_each(Lesson) \
        .join(Lesson,
              # ... in the same timeslot ...
              Joiners.equal(lambda lesson: lesson.timeslot),
              # ... in the same room ...
              Joiners.equal(lambda lesson: lesson.room),
              # form unique pairs
              Joiners.less_than(lambda lesson: lesson.id)
              ) \
        .penalize("Room conflict", HardSoftScore.ONE_HARD)


def teacher_conflict(constraint_factory):
    # A teacher can teach at most one lesson at the same time.
    return constraint_factory \
        .for_each(Lesson) \
        .join(Lesson,
              Joiners.equal(lambda lesson: lesson.timeslot),
              Joiners.equal(lambda lesson: lesson.teacher),
              Joiners.less_than(lambda lesson: lesson.id)
              ) \
        .penalize("Teacher conflict", HardSoftScore.ONE_HARD)


def student_group_conflict(constraint_factory):
    # A student can attend at most one lesson at the same time.
    return constraint_factory \
        .for_each(Lesson) \
        .join(Lesson,
              Joiners.equal(lambda lesson: lesson.timeslot),
              Joiners.equal(lambda lesson: lesson.student_group),
              Joiners.less_than(lambda lesson: lesson.id)
              ) \
        .penalize("Student group conflict", HardSoftScore.ONE_HARD)


def teacher_room_stability(constraint_factory):
    # A teacher prefers to teach in a single room.
    return constraint_factory \
        .for_each(Lesson) \
        .join(Lesson,
              Joiners.equal(lambda lesson: lesson.teacher),
              Joiners.less_than(lambda lesson: lesson.id)
              ) \
        .filter(lambda lesson1, lesson2: lesson1.room != lesson2.room) \
        .penalize("Teacher room stability", HardSoftScore.ONE_SOFT)


def teacher_time_efficiency(constraint_factory):
    # A teacher prefers to teach sequential lessons and dislikes gaps between lessons.
    return constraint_factory \
        .for_each(Lesson) \
        .join(Lesson,
              Joiners.equal(lambda lesson: lesson.teacher),
              Joiners.equal(lambda lesson: lesson.timeslot.day_of_week)
              ) \
        .filter(within_30_minutes) \
        .reward("Teacher time efficiency", HardSoftScore.ONE_SOFT)


def student_group_subject_variety(constraint_factory):
    # A student group dislikes sequential lessons on the same subject.
    return constraint_factory \
        .for_each(Lesson) \
        .join(Lesson,
              Joiners.equal(lambda lesson: lesson.subject),
              Joiners.equal(lambda lesson: lesson.student_group),
              Joiners.equal(lambda lesson: lesson.timeslot.day_of_week)
              ) \
        .filter(within_30_minutes) \
        .penalize("Student group subject variety", HardSoftScore.ONE_SOFT)


def format_list(a_list):
    return ',\n'.join(map(str, a_list))


@planning_solution
class TimeTable:
    def __init__(self, timeslot_list, room_list, lesson_list, score=None):
        self.timeslot_list = timeslot_list
        self.room_list = room_list
        self.lesson_list = lesson_list
        self.score = score
        
    def set_student_group_and_teacher_list(self):
        self.student_group_list = []
        self.teacher_list = []
        for lesson in self.lesson_list:
            if lesson.teacher not in self.teacher_list:
                self.teacher_list.append(lesson.teacher)
            if lesson.student_group not in self.student_group_list:
                self.student_group_list.append(lesson.student_group)

    @problem_fact_collection_property(Timeslot)
    @value_range_provider("timeslotRange")
    def get_timeslot_list(self):
        return self.timeslot_list

    @problem_fact_collection_property(Room)
    @value_range_provider("roomRange")
    def get_room_list(self):
        return self.room_list

    @planning_entity_collection_property(Lesson)
    def get_lesson_list(self):
        return self.lesson_list

    @planning_score(HardSoftScore)
    def get_score(self):
        return self.score

    def set_score(self, score):
        self.score = score
    
    def __str__(self):
        return (
            f"TimeTable("
            f"timeslot_list={format_list(self.timeslot_list)},\n"
            f"room_list={format_list(self.room_list)},\n"
            f"lesson_list={format_list(self.lesson_list)},\n"
            f"score={str(self.score.toString()) if self.score is not None else 'None'}"
            f")"
        )


def generate_problem():
    timeslot_list = [
        Timeslot(1, "MONDAY", time(hour=8, minute=30), time(hour=9, minute=30)),
        Timeslot(2, "MONDAY", time(hour=9, minute=30), time(hour=10, minute=30)),
        Timeslot(3, "MONDAY", time(hour=10, minute=30), time(hour=11, minute=30)),
        Timeslot(4, "MONDAY", time(hour=13, minute=30), time(hour=14, minute=30)),
        Timeslot(5, "MONDAY", time(hour=14, minute=30), time(hour=15, minute=30)),
        Timeslot(6, "TUESDAY", time(hour=8, minute=30), time(hour=9, minute=30)),
        Timeslot(7, "TUESDAY", time(hour=9, minute=30), time(hour=10, minute=30)),
        Timeslot(8, "TUESDAY", time(hour=10, minute=30), time(hour=11, minute=30)),
        Timeslot(9, "TUESDAY", time(hour=13, minute=30), time(hour=14, minute=30)),
        Timeslot(10, "TUESDAY", time(hour=14, minute=30), time(hour=15, minute=30)),
        Timeslot(11,"WEDNESDAY",time(hour=8, minute=30), time(hour=9, minute=30))
    ]
    room_list = [
        Room(1, "Room A"),
        Room(2, "Room B"),
        Room(3, "Room C")
    ]
    lesson_list = [
        Lesson(1,"Chemistry", "J.J.Sireesha", "10th B grade"),
        Lesson(2, "Mathmatics", "Gond Surjyakant", "10th C grade"),
        Lesson(3, "Physics", "Kiratkudave Snehal", "10th C grade"),
        Lesson(4, "Physics", "Kiratkudave Snehal", "9th C grade"),
        Lesson(5, "", "Shailkh Sana", "10th C grade"),
        Lesson(6, "", "Shailkh Sana", "10th A grade"),
        Lesson(7, "", "Shailkh Sana", "8th C grade"),
        Lesson(8, "Drawing", "Swati Miss", "10th C grade"),
        Lesson(9, "Drawing", "Swati Miss", "10th A grade"),
        Lesson(10, "Drawing", "Swati Miss", "7th A grade"),
        Lesson(11, "Drawing", "Swati Miss", "8th A grade"),
        Lesson(12, "Drawing", "Swati Miss", "9th C grade"),
        Lesson(13, "Drawing", "Swati Miss", "6th B grade"),
        Lesson(14, "Drawing", "Swati Miss", "6th D grade"),
        Lesson(15, "PE", "Kirti", "8th B grade"),
        Lesson(16, "PE", "Kirti", "9th B grade"),
        Lesson(17, "", "Phatare Komal", "10th C grade"),
        Lesson(18, "PE", "Chitra Rajwade", "6th B grade"),
        Lesson(19, "Computer", "Rameshwari", "10th C grade"),
        Lesson(20, "Computer", "Rameshwari", "8th D grade"),
    ]
    lesson = lesson_list[0]
    lesson.set_timeslot(timeslot_list[0])
    lesson.set_room(room_list[0])

    return TimeTable(timeslot_list, room_list, lesson_list)

solver_config = SolverConfig().withEntityClasses(Lesson) \
    .withSolutionClass(TimeTable) \
    .withConstraintProviderClass(define_constraints) \
    .withTerminationSpentLimit(Duration.ofSeconds(30))


solution = generate_problem()
solution.set_student_group_and_teacher_list()

cell_map = dict()

def on_best_solution_changed(best_solution):
    global timetable
    global solution
    global cell_map
    solution = best_solution
    unassigned_lessons = []
    clear_cell_set = set()
    
    for (table_name, table_map) in cell_map.items():
        for (key, cell) in table_map.items():
            clear_cell_set.add(cell)
            
    for lesson in solution.lesson_list:
        if lesson.timeslot is None or lesson.room is None:
            unassigned_lessons.append(lesson, clear_cell_set)
        else:
            update_lesson_in_table(lesson, clear_cell_set)
            
    for cell in clear_cell_set:
            cell.value = ""
            cell.style["backgroundColor"] = "white"
            
    for (table_name, table_map) in cell_map.items():
        for (key, cell) in table_map.items():
            cell.send_state()

def update_lesson_in_table(lesson, clear_cell_set):
    global cell_map
    x = solution.timeslot_list.index(lesson.timeslot)
    room_column = solution.room_list.index(lesson.room)
    teacher_column = solution.teacher_list.index(lesson.teacher)
    student_group_column = solution.student_group_list.index(lesson.student_group)
    


    room_cell = cell_map['room'][(x, room_column)]
    teacher_cell = cell_map['teacher'][(x, teacher_column)]
    student_group_cell = cell_map['student_group'][(x, student_group_column)]
    
    clear_cell_set.discard(room_cell)
    clear_cell_set.discard(teacher_cell)
    clear_cell_set.discard(student_group_cell)

    room_cell.value = f"{lesson.subject}\n{lesson.teacher}\n{lesson.student_group}"
   
    room_cell.send_state()

    teacher_cell.value = f"{lesson.subject}\n{lesson.student_group}"
   
    teacher_cell.send_state()

    student_group_cell.value = f"{lesson.subject}\n{lesson.teacher}"
  
    student_group_cell.send_state()

    
def create_table(table_name, solution, columns, name_map):
    global cell_map
    out = sheet(rows=len(solution.timeslot_list) + 1, columns=len(columns) + 1)
    header_color = "#22222222"
    cell(0,0, read_only=True, background_color=header_color)
    header_row = row(0, list(map(name_map, columns)), column_start=1, read_only=True,
                    background_color=header_color)
    timeslot_column = column(0,
            list(map(lambda timeslot: timeslot.day_of_week[0:3] + " " + str(timeslot.start_time)[0:10],
                             solution.timeslot_list)), row_start=1, read_only=True, background_color=header_color)

    table_cells = dict()
    cell_map[table_name] = table_cells
    for x in range(len(solution.timeslot_list)):
        for y in range(len(columns)):
            table_cells[(x, y)] = cell(x + 1, y + 1, "", read_only=True)
    return out
        
solver_manager = solver_manager_create(solver_config)

by_room_table = create_table('room', solution, solution.room_list, lambda room: room.name)
by_teacher_table = create_table('teacher', solution, solution.teacher_list, lambda teacher: teacher)
by_student_group_table = create_table('student_group', solution, solution.student_group_list,
                                      lambda student_group: student_group)

solver_manager.solveAndListen(0, lambda the_id: solution, on_best_solution_changed)

tab = Tab()
tab.children = [by_room_table, by_teacher_table, by_student_group_table]

tab.set_title(0, 'By Room')
tab.set_title(1, 'By Teacher')
tab.set_title(2, 'By Student Group')

tab

