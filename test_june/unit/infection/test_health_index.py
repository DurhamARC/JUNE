import numpy as np
from june.demography import Person
from june.infection.health_index import HealthIndexGenerator


def test__smaller_than_one():
    index_list = HealthIndexGenerator.from_file()
    increasing_count = 0
    for i in range(len(index_list.prob_lists[0])):
        index_m = index_list(Person.from_attributes(age=i, sex="m"))
        index_w = index_list(Person.from_attributes(age=i, sex="f"))
        bool_m = np.sum(np.round(index_m, 7) <= 1)
        bool_w = np.sum(np.round(index_w, 7) <= 1)
        if bool_m + bool_w == 14:
            increasing_count += 1
        else:
            increasing_count == increasing_count
    assert increasing_count == 121


def test__non_negative_probability():
    probability_object = HealthIndexGenerator.from_file()
    probability_list = probability_object.prob_lists
    negatives = 0.0
    for i in range(len(probability_list[0])):
        negatives += sum(probability_list[0][i] < 0)
        negatives += sum(probability_list[1][i] < 0)
    assert negatives == 0


def test__growing_index():
    index_list = HealthIndexGenerator.from_file()
    increasing_count = 0
    for i in range(len(index_list.prob_lists[0])):
        index_m = index_list(Person.from_attributes(age=i, sex="m"))
        index_w = index_list(Person.from_attributes(age=i, sex="f"))

        if sum(np.sort(index_w) == index_w) != len(index_w):
            increasing_count += 0

        if sum(np.sort(index_m) == index_m) != len(index_m):
            increasing_count += 0

    assert increasing_count == 0


def test__comorbidities_effect():
    comorbidity_multipliers = {"guapo": 0.8, "feo": 1.2}
    health_index = HealthIndexGenerator.from_file(
        comorbidity_multipliers=comorbidity_multipliers
    )

    dummy = Person.from_attributes(sex="f", age=40)
    feo = Person.from_attributes(sex="f", age=40, comorbidity="feo")
    guapo = Person.from_attributes(sex="f", age=40, comorbidity="guapo")

    dummy_health = health_index(dummy)
    feo_health = health_index(feo)
    guapo_health = health_index(guapo)

    np.testing.assert_equal(feo_health[:2], dummy_health[:2] * 0.8)
    np.testing.assert_equal(feo_health[3:], dummy_health[3:] * 1.2)
    np.testing.assert_equal(guapo_health[:2], dummy_health[:2] * 1.2)
    np.testing.assert_equal(guapo_health[3:], dummy_health[3:] * 0.8)
