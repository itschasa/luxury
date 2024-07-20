import sys
# remove __pycache__
sys.dont_write_bytecode = True

import waitress

import main
#main.db_migration_rowid()

try:
    main.app.logger.info('startup!')
    #waitress.serve(app=main.app, port=6983, threads=150, _quiet=True)
    main.app.run(port=6983)
finally:
    pass