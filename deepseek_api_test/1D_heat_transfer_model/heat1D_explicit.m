%% 1D Transient Heat Conduction -- Explicit Finite-Difference Solver (FTCS)
%
%  Governing equation:
%      rho*cp * dT/dt = k * d^2T/dx^2,     0 < x < L, t > 0
%
%  Initial condition:
%      T(x,0) = T_init
%
%  Physical boundary conditions (convection / Robin BCs):
%      -k*dT/dx = h_left *(T_inf_left  - T)     at x = 0
%      -k*dT/dx = h_right*(T - T_inf_right)     at x = L
%
%  Numerical method:
%      Explicit forward-time central-space (FTCS) scheme with ghost nodes
%      for the convective boundary conditions.
%      Stability criterion: Fo = alpha*dt/dx^2 <= 0.5
%
%  All quantities are in SI units (m, s, W, kg, K).  Temperatures are
%  written in degC; since only temperature differences appear in the
%  equations, using degC is equivalent to using kelvin here.
%
%  NOTE: To impose an insulated (zero-flux) boundary, simply set the
%        corresponding heat-transfer coefficient to zero, e.g. h_right = 0.

clear; clc; close all;

%% 1. Geometry and mesh
L  = 0.10;          % length of the domain [m]
N  = 51;            % number of grid points
x  = linspace(0, L, N).';
dx = x(2) - x(1);   % uniform grid spacing [m]

%% 2. Material properties (AISI 304 stainless steel)
k    = 45;          % thermal conductivity [W/(m K)]
rho  = 7850;        % density [kg/m^3]
cp   = 500;         % specific heat capacity [J/(kg K)]
alpha = k / (rho*cp);   % thermal diffusivity [m^2/s]

%% 3. Convective heat-transfer coefficients [W/(m^2 K)]
% Left boundary : hot water (forced/natural convection)
% Right boundary: ambient air (natural convection)
h_left  = 500;      % [W/(m^2 K)]
h_right = 25;       % [W/(m^2 K)]

%% 4. Initial condition and surrounding fluid temperatures
T_init       = 20;  % initial rod temperature [degC]
T_inf_left   = 100; % hot fluid temperature at x = 0 [degC]
T_inf_right  = 20;  % ambient air temperature at x = L [degC]

%% 5. Time discretization and stability check
t_end = 1000;               % simulation end time [s]
Fo    = 0.4;                % Fourier number (must be <= 0.5 for stability)
dt    = Fo * dx^2 / alpha;  % explicit time step [s]
dt_max = 0.5 * dx^2 / alpha;% maximum stable time step [s]

fprintf('dx = %.4e m,  alpha = %.4e m^2/s\n', dx, alpha);
fprintf('dt = %.4f s,  dt_max(stability) = %.4f s\n', dt, dt_max);
fprintf('Fo = %.2f (must be <= 0.50)\n\n', Fo);
if Fo > 0.5
    error('Fourier number Fo = %.3f exceeds the explicit stability limit 0.5.', Fo);
end

t   = 0:dt:t_end;           % discrete times [s]
Nt  = length(t);

%% 6. Initialize and allocate storage
T      = T_init * ones(N, 1);   % current temperature field
T_new  = T;                     % temperature at next time level
T_hist = zeros(N, Nt);          % storage for all time steps
T_hist(:, 1) = T;

%% 7. Explicit time-marching loop (FTCS)
for n = 1:Nt-1

    % -- Interior nodes: central difference in space ---------------------
    T_new(2:N-1) = T(2:N-1) + Fo*(T(3:N) - 2*T(2:N-1) + T(1:N-2));

    % -- Left boundary (convection, ghost-node method) -------------------
    % BC: -k*dT/dx = h_left*(T_inf_left - T_0)
    % Central difference with ghost node T_g gives:
    %   T_g = T_2 + (2*h_left*dx/k)*(T_inf_left - T_1)
    T_ghost_left = T(2) + (2*h_left*dx/k)*(T_inf_left - T(1));
    T_new(1)     = T(1) + Fo*(T(2) - 2*T(1) + T_ghost_left);

    % -- Right boundary (convection, ghost-node method) ------------------
    % BC: -k*dT/dx = h_right*(T_N - T_inf_right)
    % Central difference with ghost node T_g gives:
    %   T_g = T_{N-1} - (2*h_right*dx/k)*(T_N - T_inf_right)
    T_ghost_right = T(N-1) - (2*h_right*dx/k)*(T(N) - T_inf_right);
    T_new(N)      = T(N) + Fo*(T_ghost_right - 2*T(N) + T(N-1));

    % -- Advance solution and store --------------------------------------
    T = T_new;
    T_hist(:, n+1) = T;

end

fprintf('Simulation complete. Final temperatures:\n');
fprintf('  T(x=0)   = %.3f degC\n', T(1));
fprintf('  T(x=L/2) = %.3f degC\n', T(round(N/2)));
fprintf('  T(x=L)   = %.3f degC\n', T(end));

%% 8. Steady-state analytical solution for comparison
% Steady state of the 1D conduction problem with convection on both ends
% is a linear profile:  T_ss(x) = A_ss*x + B_ss.
M   = [-k,            h_left;
       (k + h_right*L), h_right];
rhs = [h_left*T_inf_left;
       h_right*T_inf_right];
coef = M \ rhs;
A_ss = coef(1);
B_ss = coef(2);
T_steady = A_ss*x + B_ss;

%% 9. Post-processing / plots

% -- Figure 1: Temperature profiles at selected times --------------------
t_plot = [0, 50, 150, 400, t_end];          % selected times [s]
T_plot = interp1(t, T_hist.', t_plot).';    % interpolate stored fields

figure('Color', 'w');
hold on; box on; grid on;
colors = lines(length(t_plot));
for i = 1:length(t_plot)
    plot(x, T_plot(:, i), '-', 'Color', colors(i, :), ...
         'LineWidth', 1.6, 'DisplayName', sprintf('t = %.0f s', t_plot(i)));
end
plot(x, T_steady, 'k--', 'LineWidth', 2, 'DisplayName', 'Steady state');
xlabel('Position x [m]');
ylabel('Temperature T [degC]');
title('1D Transient Heat Conduction (Explicit FTCS)');
legend('Location', 'eastoutside');

% -- Figure 2: Temperature history at selected locations -----------------
[~, idx_mid] = min(abs(x - L/2));
figure('Color', 'w');
hold on; box on; grid on;
plot(t, T_hist(1,      :), 'r-', 'LineWidth', 1.6, 'DisplayName', 'x = 0 (left end)');
plot(t, T_hist(idx_mid, :), 'b-', 'LineWidth', 1.6, 'DisplayName', 'x = L/2 (center)');
plot(t, T_hist(end,    :), 'g-', 'LineWidth', 1.6, 'DisplayName', 'x = L (right end)');
xlabel('Time t [s]');
ylabel('Temperature T [degC]');
title('Temperature History');
legend('Location', 'best');

% -- Figure 3: Space-time contour plot -----------------------------------
figure('Color', 'w');
contourf(x, t, T_hist.', 25, 'LineColor', 'none');
colorbar;
xlabel('Position x [m]');
ylabel('Time t [s]');
title('Space-Time Temperature Distribution');
