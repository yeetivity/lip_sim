import copy
import numpy as np
from lip2d import LIP2D
from swing_leg import SwingLeg
import step_to_step as STS
from data_storage import DataStorage


class Simulator(object):
    """
    Class which handles various simulation steps of the LIP
    """

    def __init__(self, settings):
        self.settings = settings

        # Set array for horizon scan
        self.t_step = settings.t_step
        t_horizon = settings.t_horizon
        self.horizon = np.linspace(
            self.t_step, t_horizon, int(t_horizon / self.t_step))

        # Create pendula, one for each direction
        self.lip_ap = LIP2D(
            settings.initial_com_pos_ap,
            settings.initial_com_vel_ap,
            settings.initial_cop_pos_ap,
            gravity=settings.gravity, leg_length=settings.leg_length)
        self.lip_ml = LIP2D(
            settings.initial_com_pos_ml,
            settings.initial_com_vel_ml,
            settings.initial_cop_pos_ml,
            gravity=settings.gravity, leg_length=settings.leg_length)
        self.is_right_swing = True

        # Create model for the swing leg cost
        self.swing_leg_ap = SwingLeg(
            mass=settings.mass_swing_leg,
            gravity=settings.gravity,
            leg_length=settings.swing_leg_length)
        self.swing_leg_ml = SwingLeg(
            mass=settings.mass_swing_leg,
            gravity=settings.gravity,
            leg_length=settings.swing_leg_length)

        # Data storage object
        self.sim_data = DataStorage()

        return


    def run(self, n_step=1):
        """
        Walk for predefined number of steps.
        No perturbations, constant COP during LIP swing.
        """

        # Initial swing leg angle
        initial_leg_angle_ap = self.swing_leg_ap.initial_angle
        initial_leg_angle_ml = self.swing_leg_ml.initial_angle
        if initial_leg_angle_ap is None:
            initial_leg_angle_ap = self.settings.initial_leg_angle_ap
        if initial_leg_angle_ml is None:
            initial_leg_angle_ml = self.settings.initial_leg_angle_ml

        for _ in range(0, n_step):
            
            # ==Horizon scan==
            # Simulate for each point in the horizon, assuming constant COP
            self.lip_ap.simulate(self.horizon)
            self.lip_ml.simulate(self.horizon)

            # Compute potential new foot positions based on XCOM
            offset_multiplier_ml = {True: 1, False: -1}[self.is_right_swing]
            step_pos_ap = self.lip_ap.step_location_xcom(
                offset=self.settings.xcom_offset_ap)
            step_pos_ml = self.lip_ml.step_location_xcom(
                offset=self.settings.xcom_offset_ml * offset_multiplier_ml)
            
            # Compute possible final swing leg angles based on new foot position
            final_leg_angle_ap = self.lip_ap.to_leg_angle(step_pos_ap)
            final_leg_angle_ml = self.lip_ml.to_leg_angle(step_pos_ml)
            
            # Swing leg cost computation
            swing_cost_ap = self.swing_leg_ap.compute_swing_cost(
                self.t_step, self.horizon,
                initial_leg_angle_ap, final_leg_angle_ap)
            swing_cost_ml = self.swing_leg_ml.compute_swing_cost(
                self.t_step, self.horizon,
                initial_leg_angle_ml, final_leg_angle_ml)

            # Step-to-step transition cost computation
            sts_cost = STS.transition_cost(self.settings.mass_total,
                self.lip_ap, self.lip_ml,
                step_pos_ap, step_pos_ml)

            # Cost landscape of the horizon
            total_cost = (
                self.settings.gain_swing_cost_ap * swing_cost_ap +
                self.settings.gain_swing_cost_ml * swing_cost_ml +
                self.settings.gain_sts_cost * sts_cost)

            # Find the time at which the lowest cost occurs
            index = np.argmin(total_cost)
            # ==End horizon scan==
            
            # Take a data sample for plotting
            self.sim_data.take_sample(
                self.horizon[index],
                self.lip_ap, self.lip_ml,
                step_pos_ap[index], step_pos_ml[index],
                index=index)

            # Obtain the initial swing leg angle for the next step
            initial_leg_angle_ap = self.lip_ap.to_leg_angle()[index]
            initial_leg_angle_ml = self.lip_ml.to_leg_angle()[index]
            # TODO: initial_leg_angle should be stored in swing_leg for transfer to new simulation (on copy).
            # Currently the swing leg angle of the preceding step is used, although that one is the same if steady state gait.

            # Update the models to a new global state
            self.lip_ap.override_state(
                self.lip_ap.com_pos[index],
                self.lip_ap.com_vel[index],
                step_pos_ap[index])
            self.lip_ml.override_state(
                self.lip_ml.com_pos[index],
                self.lip_ml.com_vel[index],
                step_pos_ml[index])
            
            # Change the leg
            self.is_right_swing = not self.is_right_swing

        return


    def copy_state_to(self, simulation):

        simulation.lip_ap = copy.deepcopy(self.lip_ap)
        simulation.lip_ml = copy.deepcopy(self.lip_ml)
        simulation.is_right_swing = self.is_right_swing
        simulation.swing_leg_ap = copy.deepcopy(self.swing_leg_ap)
        simulation.swing_leg_ml = copy.deepcopy(self.swing_leg_ml)

        return
