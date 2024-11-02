from pyteal import *

def clear_state_program():
    return Approve()

if __name__ == "__main__":
    compiled_clear_state = compileTeal(clear_state_program(), mode=Mode.Application, version=5)
    with open("escrow_clear_state.teal", "w") as f:
        f.write(compiled_clear_state)
