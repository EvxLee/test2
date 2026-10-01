MYDIR="$(dirname "${0}")"

# Point to sql subfolder inside db/
SQL_DIR="${MYDIR}/sql"
SQL_FILES=$(ls -1 "${SQL_DIR}"/*.sql | grep -vi "XXX-" | sort)

ATLAS_API_USER="${ATLAS_DB_API_USER:?Must provide ATLAS_DB_API_USER}"
ATLAS_API_PASSWORD="${ATLAS_DB_API_PASSWORD:?Must provide ATLAS_DB_API_PASSWORD}"

function sanity_check() {
    _RC=0
    _BINARIES=("psql")

    echo "Checking all tools are accessible..."
    for b in ${_BINARIES[*]}; do
        if ! which "${b}" >/dev/null 2>&1; then
            echo -e "\t- ERROR: You probably don't have \"${b}\" installed."
            _RC=1
        fi
    done

    echo "Checking all SQL files are readable..."
    for f in ${SQL_FILES[*]}; do
        if [[ ! -r "${f}" ]]; then
            echo -e "\t- ERROR: The SQL file \"${f}\" is not readable."
            _RC=1
        fi
    done

    if [[ ${_RC} != 0 ]]; then
        echo "ERROR: Some pre-requisites are not met, terminating!"
        exit ${_RC}
    fi
}

function run_scripts() {
    __DEFAULT_PG_URI=postgresql://postgres:changeme@localhost/atlas

    if [[ -z "${PG_URI}" ]]; then
        echo -n "Enter the Connection URI to the target database (or use the default \"${__DEFAULT_PG_URI}\"): "
        read PG_URI
        if [[ -z "${PG_URI}" ]]; then
            PG_URI="${__DEFAULT_PG_URI}"
            echo "Using the default value \"${PG_URI}\" for PG_URI."
        fi
    else
        echo "The value for \${PG_URI} is read from a variable."
    fi

    _LOG="${MYDIR}/deploy.log"
    truncate -s 0 "${_LOG}"

    echo "Cleaning out the database"
    psql "${PG_URI}" <<EOF
EOF

    for f in ${SQL_FILES[*]}; do
        echo -e "- \"${f}\"" | tee -a "${_LOG}"
        psql "${PG_URI}" \
            -v atlas_api_user="${ATLAS_API_USER}" \
            -v atlas_api_password="${ATLAS_API_PASSWORD}" \
            <"${f}" \
            2>&1 | sed "s/^/        /g" | tee -a "${_LOG}"
    done
}

sanity_check
run_scripts
