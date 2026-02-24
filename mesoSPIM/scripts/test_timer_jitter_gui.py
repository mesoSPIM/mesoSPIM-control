import sys
import time
import numpy as np
from PyQt5 import QtWidgets, QtCore

class TimerJitterTest(QtWidgets.QWidget):
    def __init__(self, interval_ms=40, num_samples=1000):
        super().__init__()
        self.interval_ms = interval_ms
        self.num_samples = num_samples
        self.timestamps = []
        self.last_time = None
        self.count = 0
        
        self.setWindowTitle(f"Timer Jitter Test - {interval_ms} ms")
        self.setGeometry(100, 100, 400, 300)
        
        # UI elements
        layout = QtWidgets.QVBoxLayout()
        
        self.label = QtWidgets.QLabel(f"Testing timer with {interval_ms} ms intervals...")
        layout.addWidget(self.label)
        
        self.progress_label = QtWidgets.QLabel("Samples: 0 / 0")
        layout.addWidget(self.progress_label)
        
        self.stats_text = QtWidgets.QTextEdit()
        self.stats_text.setReadOnly(True)
        layout.addWidget(self.stats_text)
        
        self.start_button = QtWidgets.QPushButton("Start Test")
        self.start_button.clicked.connect(self.start_test)
        layout.addWidget(self.start_button)
        
        self.setLayout(layout)
        
        # Timer
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.on_timer)
        
    def start_test(self):
        self.timestamps = []
        self.last_time = None
        self.count = 0
        self.start_button.setEnabled(False)
        self.stats_text.clear()
        self.stats_text.append(f"Starting test with {self.interval_ms} ms timer...\n")
        
        self.last_time = time.perf_counter()
        self.timer.start(self.interval_ms)
        
    def on_timer(self):
        current_time = time.perf_counter()
        
        if self.last_time is not None:
            delta_ms = (current_time - self.last_time) * 1000
            self.timestamps.append(delta_ms)
            self.count += 1
            
            self.progress_label.setText(f"Samples: {self.count} / {self.num_samples}")
            
            if self.count >= self.num_samples:
                self.timer.stop()
                self.show_statistics()
                self.start_button.setEnabled(True)
        
        self.last_time = current_time
        
    def show_statistics(self):
        intervals = np.array(self.timestamps)
        
        mean_interval = np.mean(intervals)
        median_interval = np.median(intervals)
        std_interval = np.std(intervals)
        min_interval = np.min(intervals)
        max_interval = np.max(intervals)
        
        jitter = intervals - self.interval_ms
        mean_jitter = np.mean(jitter)
        abs_jitter = np.abs(jitter)
        mean_abs_jitter = np.mean(abs_jitter)
        max_abs_jitter = np.max(abs_jitter)
        
        percentiles = np.percentile(intervals, [5, 25, 50, 75, 95])
        
        stats_text = f"""
=== Timer Jitter Statistics ===
Target interval: {self.interval_ms} ms
Number of samples: {len(intervals)}

Interval Statistics:
  Mean:     {mean_interval:.3f} ms
  Median:   {median_interval:.3f} ms
  Std Dev:  {std_interval:.3f} ms
  Min:      {min_interval:.3f} ms
  Max:      {max_interval:.3f} ms
  Range:    {max_interval - min_interval:.3f} ms

Jitter Statistics:
  Mean jitter:          {mean_jitter:.3f} ms
  Mean absolute jitter: {mean_abs_jitter:.3f} ms
  Max absolute jitter:  {max_abs_jitter:.3f} ms
  Std dev of jitter:    {std_interval:.3f} ms

Percentiles:
  5th:  {percentiles[0]:.3f} ms
  25th: {percentiles[1]:.3f} ms
  50th: {percentiles[2]:.3f} ms
  75th: {percentiles[3]:.3f} ms
  95th: {percentiles[4]:.3f} ms

Accuracy:
  Error from target: {mean_interval - self.interval_ms:.3f} ms ({(mean_interval - self.interval_ms) / self.interval_ms * 100:.2f}%)
"""
        
        self.stats_text.setText(stats_text)
        print(stats_text)


def main():
    app = QtWidgets.QApplication(sys.argv)
    
    # You can change the interval and number of samples here
    test_window = TimerJitterTest(interval_ms=40, num_samples=1000)
    test_window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
