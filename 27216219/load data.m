folder_dir = fileparts(mfilename('fullpath'));
list_files_in_folder = dir(fullfile(folder_dir,"*.mat"));

file_names = {list_files_in_folder.name};


for i=1:length(file_names)
    file_name = file_names{i};
    if file_name == "LABEL DATASET.mat"
        continue
    end
    data = importdata(file_name);
    [~, pure_name, ~] = fileparts(file_name);
    
    X = data(:,1);
    Y = data(:,2);
    Z = data(:,3);
    I1 = data(:,4);
    I2 = data(:,5);
    I3 = data(:,6);
    V1 = data(:,7);
    V2 = data(:,8);
    V3 = data(:,9);
    N = size(X,1);
    t = 1/50000*(0:N-1);
    
    % --- FIGURE 1: Vẽ các biến vị trí/tọa độ X, Y, Z ---
    figure;
    subplot(3, 1, 1); plot(t, X); title(['Acceleration X - ' pure_name]); xlabel('Time (s)'); ylabel('x (g)'); grid on;
    subplot(3, 1, 2); plot(t, Y); title(['Acceleration Y - ' pure_name]); xlabel('Time (s)'); ylabel('y (g)'); grid on;
    subplot(3, 1, 3); plot(t, Z); title(['AccelerationZ Z - ' pure_name]); xlabel('Time (s)'); ylabel('z (g)'); grid on;

    % --- FIGURE 2: Vẽ các biến I1, I2, I3 ---
    figure;
    subplot(3, 1, 1); plot(t, I1); title(['Current I1 - ' pure_name]); xlabel('Time (s)'); ylabel('I1 (A)'); grid on;
    subplot(3, 1, 2); plot(t, I2); title(['Current I2 - ' pure_name]); xlabel('Time (s)'); ylabel('I2 (A)'); grid on;
    subplot(3, 1, 3); plot(t, I3); title(['Current I3 - ' pure_name]); xlabel('Time (s)'); ylabel('I3 (A)'); grid on;

    % --- FIGURE 3: Vẽ các biến V1, V2, V3 ---
    figure;
    subplot(3, 1, 1); plot(t, V1); title(['Voltage V1 - ' pure_name]); xlabel('Time (s)'); ylabel('V1 (V)'); grid on;
    subplot(3, 1, 2); plot(t, V2); title(['Voltage V2 - ' pure_name]); xlabel('Time (s)'); ylabel('V2 (V)'); grid on;
    subplot(3, 1, 3); plot(t, V3); title(['Voltage V3 - ' pure_name]); xlabel('Time (s)'); ylabel('V3 (V)'); grid on;
end

