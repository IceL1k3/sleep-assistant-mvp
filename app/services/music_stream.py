
class StreamBuffer:
    def __init__(self):
        self.current_chunk: str = ''   # Чанк А (играет)
        self.next_chunk: str = ''      # Чанк B (ждет)
        self.generating_chunk: str = '' # Чанк C (пишется ИИ)




