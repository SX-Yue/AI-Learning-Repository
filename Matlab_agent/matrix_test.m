%% ============================================================
%  matrix_test.m - MATLAB 综合测试脚本
%  测试内容：矩阵运算 / 线性方程组 / 循环条件 / 函数调用
%  Author: MATLAB Agent
%% ============================================================
clc; clear; close all;

fprintf('========== MATLAB 综合测试开始 ==========\n\n');

%% 1. 基础矩阵运算
fprintf('--- 1. 基础矩阵运算 ---\n');
A = [1 2 3; 4 5 6; 7 8 10];      % 可逆矩阵（非奇异）
B = [1 0 1; 0 1 0; 1 0 1];

fprintf('矩阵 A =\n'); disp(A);
fprintf('矩阵 B =\n'); disp(B);
fprintf('A + B =\n'); disp(A + B);
fprintf('A * B =\n'); disp(A * B);
fprintf('A 的转置 A^T =\n'); disp(A');
fprintf('det(A) = %.4f\n\n', det(A));

%% 2. 矩阵求逆与验证
fprintf('--- 2. 矩阵求逆与验证 ---\n');
Ainv = inv(A);
fprintf('inv(A) =\n'); disp(Ainv);
fprintf('验证 A * inv(A) 是否为单位阵：\n'); disp(A * Ainv);
fprintf('最大误差 = %.2e\n\n', max(abs(A * Ainv - eye(3)), [], 'all'));

%% 3. 求解线性方程组 A*x = b
fprintf('--- 3. 求解线性方程组 ---\n');
b = [1; 2; 3];
x = A \ b;                          % 推荐方式：左除
fprintf('b =\n'); disp(b);
fprintf('解 x = A \\ b =\n'); disp(x);
fprintf('验证 A*x - b 的残差 = %.2e\n\n', norm(A*x - b));

%% 4. 循环与条件语句（计算 1~10 的平方与奇偶判断）
fprintf('--- 4. 循环与条件语句 ---\n');
for i = 1:10
    sq = i^2;
    if mod(i, 2) == 0
        type_str = '偶数';
    else
        type_str = '奇数';
    end
    fprintf('%2d 的平方 = %3d  (%s)\n', i, sq, type_str);
end
fprintf('\n');

%% 5. 匿名函数与函数调用
fprintf('--- 5. 匿名函数 ---\n');
f = @(x) x.^2 + 2*x + 1;           % f(x) = x^2 + 2x + 1
xvals = 0:5;
fprintf('f(x) = x^2 + 2x + 1 在 x=0..5 的值:\n');
disp(f(xvals));

%% 6. 绘图示例
fprintf('--- 6. 绘图示例 ---\n');
t = linspace(0, 2*pi, 100);
y1 = sin(t);
y2 = cos(t);
figure('Name', 'Sin & Cos');
plot(t, y1, 'r-', 'LineWidth', 2); hold on;
plot(t, y2, 'b--', 'LineWidth', 2);
grid on; legend('sin(t)', 'cos(t)');
xlabel('t'); ylabel('y'); title('sin(t) 与 cos(t) 曲线');
saveas(gcf, fullfile(pwd, 'sin_cos_plot.png'));
fprintf('图形已保存为: %s\n\n', fullfile(pwd, 'sin_cos_plot.png'));

%% 7. 统计功能
fprintf('--- 7. 统计功能 ---\n');
data = randn(1, 1000);              % 1000 个标准正态随机数
fprintf('均值 = %.4f\n', mean(data));
fprintf('标准差 = %.4f\n', std(data));
fprintf('最大值 = %.4f\n', max(data));
fprintf('最小值 = %.4f\n', min(data));
fprintf('中位数 = %.4f\n\n', median(data));

fprintf('========== MATLAB 综合测试结束 ==========\n');
