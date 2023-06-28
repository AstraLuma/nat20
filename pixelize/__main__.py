import logging

from textual.logging import TextualHandler

from pixelize import PixelsApp

logging.basicConfig(
    level="NOTSET",
    handlers=[TextualHandler()],
)

PixelsApp().run()
