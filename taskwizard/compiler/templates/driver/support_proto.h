#include <cstdio>

void driver_init();

int algorithm_start(const char *algo_name);

int algorithm_status(int algorithm_id);
int algorithm_kill(int algorithm_id);

FILE *algorithm_input_pipe(int algorithm_id);
FILE *algorithm_output_pipe(int algorithm_id);


int read_file_open(const char *file_name);
FILE *read_file_pipe(int id);
int read_file_close(int id);


int write_file_open(const char *file_name);
FILE *write_file_pipe(int id);
int write_file_close(int id);
