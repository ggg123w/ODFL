int printf(const char *format, ...);
static short d;
long e;
long *g = &e;
int h;
int i(int j) {
  int c = 1;
  for (;; c++)
    if (1 << c >= j)
      return c;
}

void l(int j) {
  int m, o = (j + 83)%12;
  h = -o + 9;
  unsigned n = h;
  m = n >= 32 ? 1 : 1 >> n;
  if (m)
    *g = j;
  short *a = &d, *b = &a;
  b || 0;
}
void p() {
  int q = i(d - 8);
  printf("%d\n", q);
  l(-q);
}
int main() {
  p();
  printf("%d\n", e);
}
