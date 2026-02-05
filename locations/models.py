from django.db import models

class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __str__(self): return self.name

class State(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='states', null=True, blank=True)
    name = models.CharField(max_length=100)
    def __str__(self): return f"{self.name} ({self.country.name if self.country else 'No Country'})"

class District(models.Model):
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name='districts')
    name = models.CharField(max_length=100)
    def __str__(self): return f"{self.name} ({self.state.name})"

class Mandal(models.Model):
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name='mandals')
    name = models.CharField(max_length=100)
    def __str__(self): return f"{self.name} ({self.district.name})"

class Village(models.Model):
    mandal = models.ForeignKey(Mandal, on_delete=models.CASCADE, related_name='villages')
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    
    def __str__(self): return f"{self.name}, {self.mandal.name}"