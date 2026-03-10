from django.http import JsonResponse
from .models import State, District, Mandal, Village

def load_states(request):
    country_id = request.GET.get('country_id')
    states = State.objects.filter(country_id=country_id).values('id', 'name')
    return JsonResponse(list(states), safe=False)

def load_districts(request):
    state_id = request.GET.get('state_id')
    districts = District.objects.filter(state_id=state_id).values('id', 'name')
    return JsonResponse(list(districts), safe=False)

def load_mandals(request):
    district_id = request.GET.get('district_id')
    mandals = Mandal.objects.filter(district_id=district_id).values('id', 'name')
    return JsonResponse(list(mandals), safe=False)

def load_villages(request):
    mandal_id = request.GET.get('mandal_id')
    villages = Village.objects.filter(mandal_id=mandal_id).select_related('mandal__district')
    data = [
        {
            'id': village.id,
            'name': village.name,
            'label': f"{village.name} ({village.mandal.name}, {village.mandal.district.name})"
        }
        for village in villages
    ]
    return JsonResponse(data, safe=False)
