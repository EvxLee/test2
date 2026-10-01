from psycopg import Connection
import traceback

def hydrate_monday_from_staging(conn: Connection) -> None:
    print("\n--- HYDRATE START ---", flush=True)
    try:
        print("[HYDRATE] running main logic...", flush=True)
        with conn.cursor() as cur:
            cur.execute("SELECT monday.hydrate_from_staging();")
        conn.commit()

        print("--- HYDRATE END OK ---", flush=True)

    except Exception:
        print("\n*** HYDRATE TRACEBACK ***", flush=True)
        traceback.print_exc()
        print("*** END HYDRATE TRACEBACK ***\n", flush=True)
        raise

