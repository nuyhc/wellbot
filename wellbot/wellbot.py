
import reflex as rx


class State(rx.State):
    num = 0

    def decrease(self):
        self.num -= 1

    def increase(self):
        self.num += 1


def index():
    return rx.container(
            rx.hstack(
                rx.button("Decrease", on_click=State.decrease, color_scheme="ruby"),
                rx.text(State.num, font_size="1.5em"),
                rx.button("Increase", on_click=State.increase, color_scheme="grass"),
                spacing="4",
                )
            )


app = rx.App()
app.add_page(index)
