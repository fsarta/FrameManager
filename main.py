"""
main.py
-------
Entry point del progetto Frame3D Manager.

Avvio rapido
------------
    python main.py

Requisiti
---------
    pip install open3d numpy scipy

Versioni testate
----------------
    open3d  >= 0.17
    numpy   >= 1.21
    scipy   >= 1.7
    Python  >= 3.8
"""

from app import Frame3DApp


if __name__ == "__main__":
    app = Frame3DApp()
    app.run()
