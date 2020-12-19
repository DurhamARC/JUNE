import numpy as np
import pandas as pd
import yaml
from typing import Optional, List

from june.infection.symptom_tag import SymptomTag
from june import paths
from june.utils.parse_probabilities import parse_age_probabilities
from . import Data2Rates

_sex_short_to_long = {"m": "male", "f": "female"}
index_to_maximum_symptoms_tag = {
    0: "asymptomatic",
    1: "mild",
    2: "severe",
    3: "hospitalised",
    4: "intensive_care",
    5: "dead_home",
    6: "dead_hospital",
    7: "dead_icu",
}

default_rates_file = paths.data_path / "input/health_index/infection_outcome_rates.csv"

def _parse_interval(interval):
    age1, age2 = interval.split(",")
    age1 = int(age1.split("[")[-1])
    age2 = int(age2.split("]")[0])
    return pd.Interval(left=age1, right=age2, closed="both")

class HealthIndexGenerator:
    def __init__(self, rates_df: pd.DataFrame, care_home_min_age: int = 50, max_age=99, use_comorbidities: bool = False, comorbidity_multipliers: Optional[dict]=None, comorbidity_prevalence_reference_population: Optional[dict]=None):
        """
        A Generator to determine the final outcome of an infection.

        Parameters
        ----------
        rates_df
            a dataframe containing all the different outcome rates,
            check the default file for a reference
        care_home_min_age
            the age from which a care home resident follows the health index
            for care homes.
        """
        self.care_home_min_age = care_home_min_age
        self.rates_df = rates_df
        self.age_bins = self.rates_df.index
        self.probabilities = self._get_probabilities(max_age)
        self.use_comorbidities = use_comorbidities
        if self.use_comorbidities:
            self.comorbidity_multipliers = comorbidity_multipliers
            self.comorbidity_prevalence_reference_population = comorbidity_prevalence_reference_population
            self._parse_prevalence_comorbidities_in_reference_population()

    @classmethod
    def from_file(cls, rates_file: str = default_rates_file, care_home_min_age=50):
        ifrs = pd.read_csv(rates_file, index_col=0)
        ifrs = ifrs.rename(_parse_interval)
        return cls(rates_df=ifrs, care_home_min_age=care_home_min_age)

    def __call__(self, person):
        """
        Computes the probability of having all 8 posible outcomes for all ages between 0 and 100,
        for male and female
        """
        if (
            person.residence is not None
            and person.residence.group.spec == "care_home"
            and person.age >= self.care_home_min_age
        ):
            population = "ch"
        else:
            population = "gp"
        probabilities = self.probabilities[population][
            person.sex
        ][person.age]
        return np.cumsum(probabilities)

    def get_multiplier_from_reference_prevalence(self, age, sex):
        """
        Compute mean comorbidity multiplier given the prevalence of the different comorbidities
        in the reference population (for example the UK). It will be used to remove effect of 
        comorbidities in the reference population

        Parameters
        ----------
        age:
            age group to compute average multiplier
        sex:
            sex group to compute average multiplier
        Returns
        -------
            weighted_multiplier:
                weighted mean of the multipliers given prevalence
        """
        weighted_multiplier = 0.0
        for (
            comorbidity
        ) in self.comorbidity_prevalence_reference_population.keys():
            weighted_multiplier += (
                self.comorbidity_multipliers[comorbidity]
                * self.comorbidity_prevalence_reference_population[
                    comorbidity
                ][sex][age]
            )
        return weighted_multiplier

    def _set_probability_per_age_bin(self, p, age_bin, sex, population):
        _sex = _sex_short_to_long[sex]
        asymptomatic_rate = self.rates_df.loc[
            age_bin, f"{population}_asymptomatic_{_sex}"
        ]
        mild_rate = self.rates_df.loc[age_bin, f"{population}_mild_{_sex}"]
        hospital_rate = self.rates_df.loc[age_bin, f"{population}_hospital_{_sex}"]
        icu_rate = self.rates_df.loc[age_bin, f"{population}_icu_{_sex}"]
        home_dead_rate = self.rates_df.loc[age_bin, f"{population}_home_ifr_{_sex}"]
        hospital_dead_rate = self.rates_df.loc[
            age_bin, f"{population}_hospital_ifr_{_sex}"
        ]
        icu_dead_rate = self.rates_df.loc[age_bin, f"{population}_icu_ifr_{_sex}"]
        severe_rate = max(
            0,
            1 - (hospital_rate + home_dead_rate + asymptomatic_rate + mild_rate),
        )
        # fill each age in bin
        for age in range(age_bin.left, age_bin.right + 1):
            p[population][sex][age][0] = asymptomatic_rate  # recovers as asymptomatic
            p[population][sex][age][1] = mild_rate  # recovers as mild
            p[population][sex][age][2] = severe_rate  # recovers as severe
            p[population][sex][age][3] = (
                hospital_rate - hospital_dead_rate
            )  # recovers in the ward
            p[population][sex][age][4] = max(
                icu_rate - icu_dead_rate, 0
            )  # recovers in the icu
            p[population][sex][age][5] = max(home_dead_rate, 0)  # dies at home
            p[population][sex][age][6] = max(
                hospital_dead_rate - icu_dead_rate, 0
            )  # dies in the ward
            p[population][sex][age][7] = icu_dead_rate
            total = np.sum(p[population][sex][age])
            p[population][sex][age] = p[population][sex][age] / total

    def _get_probabilities(self, max_age=99):
        n_outcomes = 8
        probabilities = {
            "ch": {
                "m": np.zeros((max_age + 1, n_outcomes)),
                "f": np.zeros((max_age + 1, n_outcomes)),
            },
            "gp": {
                "m": np.zeros((max_age + 1, n_outcomes)),
                "f": np.zeros((max_age + 1, n_outcomes)),
            },
        }
        for population in ("ch", "gp"):
            for sex in ["m", "f"]:
                # values are constant at each bin
                for age_bin in self.age_bins:
                    self._set_probability_per_age_bin(
                        p=probabilities,
                        age_bin=age_bin,
                        sex=sex,
                        population=population,
                    )
        return probabilities

    def _parse_prevalence_comorbidities_in_reference_population(self,):
        for comorbidity, values in self.comorbidity_prevalence_reference_population.items():
            self.comorbidity_prevalence_reference_population[comorbidity] = {
                    'f': parse_age_probabilities(values['f']),
                    'm': parse_age_probabilities(values['m']),
            }
