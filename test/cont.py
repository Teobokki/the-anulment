import traceback
def go(t):
    app.start_game(); return t.done
def chk(t):
    try:
        g = app.game; print("CONTINUE stage", g.stage, "published", g.published, "posts", g.posts, "tip", g.tip, "obj", g.obj_t.getText().replace(chr(10), " | "), "cut", g.cut, flush=True)
    except Exception: traceback.print_exc()
    app.userExit()
app.do_method_later(1, go, "g"); app.do_method_later(10, chk, "c")
