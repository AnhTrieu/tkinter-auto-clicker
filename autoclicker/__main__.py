from .dpi import set_dpi_awareness
from .ui import AutoClickerApp


def main() -> None:
    dpi_mode = set_dpi_awareness()
    app = AutoClickerApp(dpi_mode=dpi_mode)
    app.mainloop()


if __name__ == "__main__":
    main()

