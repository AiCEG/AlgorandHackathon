from pyteal import *


ESCROW_TIMEOUT = Int(10000) 
ADMIN_ADDRESS = Addr("ADMIN_ALGORAND_ADDRESS")  

# Global State Keys
global_escrow_counter = Bytes("escrow_counter")  
global_blacklist = Bytes("blacklist")            

def approval_program():
    op = Txn.application_args[0]

    def is_admin():
        return Txn.sender() == ADMIN_ADDRESS

    def initiate_escrow():
        # Expected arguments: ["initiate_escrow", seller_address, product_id, amount]
        Assert(Txn.application_args.length() == Int(4))

        seller = Txn.application_args[1]
        product_id = Txn.application_args[2]
        amount = Btoi(Txn.application_args[3])

        buyer_blacklisted = App.globalGetEx(Int(0), Concat(global_blacklist, Txn.sender()))
        seller_blacklisted = App.globalGetEx(Int(0), Concat(global_blacklist, seller))

        escrow_id = App.globalGet(global_escrow_counter)
        increment_escrow_id = App.globalPut(global_escrow_counter, escrow_id + Int(1))

        escrow_key = Concat(Bytes("escrow_"), Itob(escrow_id))
        escrow_data = Concat(
            Txn.sender(),
            seller,      
            Itob(amount),
            product_id,  
            Itob(Global.round()), 
            Bytes("pending")   
        )

        return Seq([
            buyer_blacklisted,
            seller_blacklisted,
            Assert(Not(buyer_blacklisted.hasValue())),
            Assert(Not(seller_blacklisted.hasValue())),
            App.globalPut(escrow_key, escrow_data),
            increment_escrow_id,
            Approve()
        ])

    def confirm_delivery():
        # Expected arguments: ["confirm_delivery", escrow_id]
        Assert(Txn.application_args.length() == Int(2))

        escrow_id = Btoi(Txn.application_args[1])
        escrow_key = Concat(Bytes("escrow_"), Itob(escrow_id))
        escrow_data = App.globalGet(escrow_key)

        buyer = Extract(escrow_data, Int(0), Int(32))
        seller = Extract(escrow_data, Int(32), Int(32))
        amount = Btoi(Extract(escrow_data, Int(64), Int(8)))
        status = Extract(escrow_data, Len(escrow_data) - Int(7), Int(7))

        new_escrow_data = Concat(
            Extract(escrow_data, Int(0), Len(escrow_data) - Int(7)),
            Bytes("complete")
        )

        return Seq([
            Assert(Txn.sender() == buyer),
            Assert(status == Bytes("pending")),
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.Payment,
                TxnField.receiver: seller,
                TxnField.amount: amount,
                TxnField.fee: Int(1000), 
            }),
            InnerTxnBuilder.Submit(),
            
            App.globalPut(escrow_key, new_escrow_data),
            Approve()
        ])

    program = Cond(
        [Txn.application_id() == Int(0), Seq([
            App.globalPut(global_escrow_counter, Int(0)),
            Approve()
        ])],  
        [Txn.on_completion() == OnComplete.DeleteApplication, Return(is_admin())],
        [Txn.on_completion() == OnComplete.UpdateApplication, Return(is_admin())],
        [Txn.on_completion() == OnComplete.CloseOut, Approve()],
        [Txn.on_completion() == OnComplete.OptIn, Approve()],
        [op == Bytes("initiate_escrow"), initiate_escrow()],
        [op == Bytes("confirm_delivery"), confirm_delivery()],
        [Int(1), Reject()]
    )

    return program

if __name__ == "__main__":
    compiled_approval = compileTeal(approval_program(), mode=Mode.Application, version=5)
    with open("escrow_approval.teal", "w") as f:
        f.write(compiled_approval)
