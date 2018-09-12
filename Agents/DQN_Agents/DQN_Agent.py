
from Agents.Base_Agent import Base_Agent
from Memory_Data_Structures.Replay_Buffer import Replay_Buffer
from Networks.NN_Creators import create_vanilla_NN
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.autograd import Variable
import random
import numpy as np


class DQN_Agent(Base_Agent):
    
    def __init__(self, environment, seed, hyperparameters, rolling_score_length, average_score_required,
                 agent_name):
        Base_Agent.__init__(self, environment=environment, 
                            seed=seed, hyperparameters=hyperparameters, rolling_score_length=rolling_score_length,
                            average_score_required=average_score_required, agent_name=agent_name)

        self.memory = Replay_Buffer(self.hyperparameters["buffer_size"],
                                    self.hyperparameters["batch_size"], seed)

        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

        self.qnetwork_local = create_vanilla_NN(self.state_size, self.action_size, seed, self.hyperparameters).to(self.device)

            # Vanilla_NN(self.state_size, self.action_size, seed, hyperparameters).get_model().to(self.device)

        self.optimizer = optim.Adam(self.qnetwork_local.parameters(), lr=self.hyperparameters["learning_rate"])

    def pick_and_conduct_action(self):
        self.action = self.pick_action()
        self.conduct_action()

    def pick_action(self):
        
        state = torch.from_numpy(self.state).float().unsqueeze(0).to(self.device) #gets state in format ready for network

        self.qnetwork_local.eval() #puts network in evaluation mode
        with torch.no_grad():
            action_values = self.qnetwork_local(state)        
        self.qnetwork_local.train() #puts network back in training mode        
        
        action = self.make_epsilon_greedy_choice(action_values)
        
        return action
            
    def make_epsilon_greedy_choice(self, action_values):
        
        epsilon = self.hyperparameters["epsilon"] / (1.0 + self.episode_number / 200.0)
        
        if random.random() > epsilon:
            return np.argmax(action_values.cpu().data.numpy())
        return random.choice(np.arange(self.action_size))
    
    def learn(self):
        if self.time_to_learn():
            states, actions, rewards, next_states, dones = self.sample_experiences() #Sample experiences                        
            loss = self.compute_loss(states, next_states, rewards, actions, dones) #Compute the loss
            self.take_optimisation_step(loss) #Take an optimisation step            
    
    def compute_loss(self, states, next_states, rewards, actions, dones):
        
        Q_targets = self.compute_q_targets(next_states, rewards, dones)
        Q_expected = self.compute_expected_q_values(states, actions)        
        loss = F.mse_loss(Q_expected, Q_targets)
        
        return loss    
    
    def compute_q_targets(self, next_states, rewards, dones):
        
        Q_targets_next = self.compute_q_values_for_next_states(next_states)
        Q_targets = self.compute_q_values_for_current_states(rewards, Q_targets_next, dones)
        return Q_targets            
    
    def compute_q_values_for_next_states(self, next_states):
        Q_targets_next = self.qnetwork_local(next_states).detach().max(1)[0].unsqueeze(1)
        return Q_targets_next    
        
    def compute_q_values_for_current_states(self, rewards, Q_targets_next, dones):
        Q_targets_current = rewards + (self.hyperparameters["gamma"] * Q_targets_next * (1 - dones))
        return Q_targets_current
    
    def compute_expected_q_values(self, states, actions):

        Q_expected = self.qnetwork_local(states).gather(1, actions.long()) #must convert actions to long so can be used as index
        
        return Q_expected
        
    def take_optimisation_step(self, loss):
        
        self.optimizer.zero_grad() #reset gradients to 0
        loss.backward() #this calculates the gradients
        self.optimizer.step() #this applies the gradients

    def save_experience(self):
        self.memory.add(self.state, self.action, self.reward, self.next_state, self.done)
        
    def locally_save_policy(self):
        torch.save(self.qnetwork_local.state_dict(), "Models/{}_local_network.pt".format(self.agent_name))
    
            
    def time_to_learn(self):
        return self.right_amount_of_steps_taken() and self.enough_experiences_to_learn_from()

    def right_amount_of_steps_taken(self):
        return self.step_number % self.hyperparameters["update_every_n_steps"] == 0

    def enough_experiences_to_learn_from(self):
        return len(self.memory) > self.hyperparameters["batch_size"]

    def sample_experiences(self):
        experiences = self.memory.sample()
        states, actions, rewards, next_states, dones = experiences
        return states, actions, rewards, next_states, dones


