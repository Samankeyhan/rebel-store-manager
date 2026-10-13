"""python -m tools.integrity_check [--db PATH]: a READ-ONLY command that tells whether the numbers in the database agree with
each other (settlements, orders, stock, unit costs, invoice numbers, distributions, name collisions).
Exit 0 = OK, 1 = problems found, 2 = could not run (or a check could not run). It never writes: see readonly.py."""
