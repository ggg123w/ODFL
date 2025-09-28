int a, b, c = -1;

void f (int e)
{
  b = b % ~(c * e) * e;
}

int main ()
{
  f (0 || a);
  return 0; 
}