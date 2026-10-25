class ThinkSplitter:
    """Incrementally split R1 think tags, including tags divided across token chunks."""

    def __init__(self, thinking=False):
        self.thinking = thinking
        self.buffer = ""

    def feed(self, text, final=False):
        self.buffer += text
        output, reasoning = [], []
        while self.buffer:
            tag = "</think>" if self.thinking else "<think>"
            index = self.buffer.find(tag)
            if index >= 0:
                (reasoning if self.thinking else output).append(self.buffer[:index])
                self.buffer = self.buffer[index + len(tag) :]
                self.thinking = not self.thinking
                continue
            keep = 0
            if not final:
                for size in range(1, min(len(tag), len(self.buffer) + 1)):
                    if self.buffer.endswith(tag[:size]):
                        keep = size
            segment = self.buffer[:-keep] if keep else self.buffer
            (reasoning if self.thinking else output).append(segment)
            self.buffer = self.buffer[-keep:] if keep else ""
            break
        return "".join(output), "".join(reasoning)
