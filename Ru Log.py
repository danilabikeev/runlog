# main.py (обновленная версия)
class RunLogApp(RunLogOfflineMixin):
    """Обновленное приложение с поддержкой оффлайн-режима"""
    
    def __init__(self):
        RunLogOfflineMixin.__init__(self)
        
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("RunLog")
        
        # Инициализация компонентов
        self.database = Database()
        self.database.initialize()
        
        # Настройка оффлайн-режима
        self.setup_offline_ui()
        
        # Создание главного окна
        self.main_window = MainWindow(self)
        self.main_window.show()
        
        # Мониторинг состояния сети
        self.start_network_monitor()
        
        sys.exit(self.app.exec())
    
    def start_network_monitor(self):
        """Запуск монитора сети в UI"""
        self.network_timer = QTimer()
        self.network_timer.timeout.connect(self.check_network_status)
        self.network_timer.start(5000)  # Проверка каждые 5 секунд
    
    def check_network_status(self):
        """Проверка статуса сети"""
        was_online = self.offline_manager.is_online
        is_online = self.offline_manager.check_online_status()
        
        if was_online != is_online:
            self.update_connection_indicator()
            
            if is_online and not was_online:
                self.on_connection_restored()
    
    def on_connection_restored(self):
        """Действия при восстановлении соединения"""
        reply = QMessageBox.question(
            self.main_window,
            "Соединение восстановлено",
            "Синхронизировать данные с сервером?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.manual_sync()