"""Phase 83.3 — unseen sentence moulds from the reserved set v5 (family iii, the coverage lever), one parametrised case per
v5 miss that a grounded detector can serve (values copied from the user's words). Failing first."""
from __future__ import annotations

import pytest

from hmgfu.facts import FactStore


def _run(tmp_path, text, prior=()):
    tmp_path.mkdir(parents=True, exist_ok=True)
    st = FactStore(str(tmp_path / "f.db"))
    for m in prior:
        st.apply_all(m, "user_explicit")
    before = {f["key"]: f["value"] for f in st.active()}
    st.apply_all(text, "user_explicit")
    after = {f["key"]: f["value"] for f in st.active()}
    return {k: v for k, v in after.items() if before.get(k) != v}


CASES = [
    # identity.name
    ("Let me introduce myself properly: Marta Sitoe, at your service.", {"identity.name": "Marta Sitoe"}),
    ("Deixa-me apresentar-me como deve ser: Marta Sitoe, ao teu dispor.", {"identity.name": "Marta Sitoe"}),
    ("The name's Élio Mabunda, though most people never get the accent right.", {"identity.name": "Élio Mabunda"}),
    ("O nome é Élio Mabunda, embora quase ninguém acerte no acento.", {"identity.name": "Élio Mabunda"}),
    ("For your records: full name Sérgio Paulo Nhaca.", {"identity.name": "Sérgio Paulo Nhaca"}),
    ("Para os teus registos: nome completo Sérgio Paulo Nhaca.", {"identity.name": "Sérgio Paulo Nhaca"}),
    ("Hi there, Bernardo here.", {"identity.name": "Bernardo"}),
    ("Olá, aqui é o Bernardo.", {"identity.name": "Bernardo"}),
    ("I am Happy, that's my actual name.", {"identity.name": "Happy"}),
    ("Chamo-me Feliz, é mesmo o meu nome.", {"identity.name": "Feliz"}),
    ("Quick facts: name Joel, city Nampula, job welder.", {"identity.name": "Joel", "identity.location": "Nampula", "identity.job": "welder"}),
    ("Factos rápidos: nome Joel, cidade Nampula, profissão soldador.", {"identity.name": "Joel", "identity.location": "Nampula", "identity.job": "soldador"}),
    # identity.alias
    ("Os amigos tratam-me por Dudu, podes fazer o mesmo.", {"identity.alias": "Dudu"}),
    ("Please address me as Dr. Mondlane from now on.", {"identity.alias": "Dr. Mondlane"}),
    ("Trata-me por Doutor Mondlane daqui em diante.", {"identity.alias": "Doutor Mondlane"}),
    ("Chama-me só Zé.", {"identity.alias": "Zé"}),
    ("I go by Nina these days.", {"identity.alias": "Nina"}),
    ("Hoje em dia sou conhecida por Nina.", {"identity.alias": "Nina"}),
    # identity.location
    ("I've settled in Quelimane for good.", {"identity.location": "Quelimane"}),
    ("Assentei de vez em Quelimane.", {"identity.location": "Quelimane"}),
    ("Home base is Tete these days.", {"identity.location": "Tete"}),
    ("A minha base agora é Tete.", {"identity.location": "Tete"}),
    ("I relocated to Pemba in January.", {"identity.location": "Pemba"}),
    ("Mudei de casa para Pemba em Janeiro.", {"identity.location": "Pemba"}),
    ("I'm currently residing in Lichinga.", {"identity.location": "Lichinga"}),
    ("We've made Xai-Xai our home.", {"identity.location": "Xai-Xai"}),
    ("Fizemos de Xai-Xai a nossa casa.", {"identity.location": "Xai-Xai"}),
    ("I'm based out of Chimoio for work and life.", {"identity.location": "Chimoio"}),
    ("Estou a viver em Chimoio, por trabalho e por gosto.", {"identity.location": "Chimoio"}),
    ("Living in Inhambane now, near the beach.", {"identity.location": "Inhambane"}),
    ("A viver em Inhambane, perto da praia.", {"identity.location": "Inhambane"}),
    ("Since 2021 my home has been Nampula.", {"identity.location": "Nampula"}),
    ("Desde 2021 que a minha casa é Nampula.", {"identity.location": "Nampula"}),
    ("I moved from Tete to Quelimane last week.", {"identity.location": "Quelimane"}),
    ("Mudei-me de Tete para Quelimane na semana passada.", {"identity.location": "Quelimane"}),
    # identity.job / company
    ("I earn my living as a midwife.", {"identity.job": "midwife"}),
    ("Ganho a vida como parteira.", {"identity.job": "parteira"}),
    ("By profession I'm an electrician.", {"identity.job": "electrician"}),
    ("O meu cargo é analista de dados.", {"identity.job": "analista de dados"}),
    ("I'm a nurse.", {"identity.job": "nurse"}),
    ("I'm an accountant at a small firm.", {"identity.job": "accountant"}),
    ("I'm employed at Millennium bim as a teller.", {"identity.company": "Millennium bim", "identity.job": "teller"}),
    ("Trabalho no Millennium bim como caixa.", {"identity.company": "Millennium bim", "identity.job": "caixa"}),
    ("A minha entidade patronal é a Vodacom.", {"identity.company": "Vodacom"}),
    # birthday
    ("I celebrate my birthday every 2 February.", {"identity.birthday": "2 February"}),
    ("Faço anos todos os dias 2 de Fevereiro.", {"identity.birthday": "2 de Fevereiro"}),
    # preferences
    ("If I had to pick one colour for everything it would be indigo.", {"pref.color": "indigo"}),
    ("Se tivesse de escolher uma cor para tudo seria o índigo.", {"pref.color": "índigo"}),
    ("Cor favorita: verde-oliva.", {"pref.color": "verde-oliva"}),
    ("Nothing beats mustard yellow in my book.", {"pref.color": "mustard yellow"}),
    ("Não há cor que bata o amarelo-mostarda, para mim.", {"pref.color": "amarelo-mostarda"}),
    ("Turquoise is the colour I keep coming back to.", {"pref.color": "Turquoise"}),
    ("O turquesa é a cor a que volto sempre.", {"pref.color": "turquesa"}),
    ("My favourite colour has always been indigo, since I was a child.", {"pref.color": "indigo"}),
    ("A minha cor favorita sempre foi o índigo, desde criança.", {"pref.color": "índigo"}),
    ("I always order rooibos tea.", {"pref.drink": "rooibos tea"}),
    ("Peço sempre chá de rooibos.", {"pref.drink": "chá de rooibos"}),
    ("Coffee-wise, I only drink espresso.", {"pref.drink": "espresso"}),
    ("Em café, só bebo expresso.", {"pref.drink": "expresso"}),
    ("Give me xima with matapa over any other meal.", {"pref.food": "xima with matapa"}),
    ("Dá-me xima com matapa em vez de qualquer outra refeição.", {"pref.food": "xima com matapa"}),
    ("I could eat grilled prawns every single day.", {"pref.food": "grilled prawns"}),
    ("Comia camarão grelhado todos os dias.", {"pref.food": "camarão grelhado"}),
    ("Food-wise, my weakness is badjias.", {"pref.food": "badjias"}),
    ("Em termos de comida, a minha fraqueza são badjias.", {"pref.food": "badjias"}),
    ("I write most of my code in Kotlin nowadays.", {"pref.language": "Kotlin"}),
    ("Escrevo a maior parte do meu código em Kotlin hoje em dia.", {"pref.language": "Kotlin"}),
    ("TypeScript is my go-to language.", {"pref.language": "TypeScript"}),
    ("TypeScript é a minha linguagem de eleição.", {"pref.language": "TypeScript"}),
    ("Desenvolvo sobretudo em Swift.", {"pref.language": "Swift"}),
    ("I'm a Kotlin developer.", {"pref.language": "Kotlin", "identity.job": "developer"}),
    ("Sou programador de Kotlin.", {"pref.language": "Kotlin", "identity.job": "programador"}),
    ("The music I listen to most is pandza.", {"pref.music": "pandza"}),
    ("A música que mais oiço é pandza.", {"pref.music": "pandza"}),
    ("Music-wise I'm all about amapiano.", {"pref.music": "amapiano"}),
    ("Em música, é só amapiano.", {"pref.music": "amapiano"}),
    ("I support Sporting de Lisboa.", {"pref.team": "Sporting de Lisboa"}),
    # pets, family, links
    ("We adopted a kitten and named her Pipoca.", {"pet.cat.name": "Pipoca"}),
    ("Adoptámos uma gatinha e chamámos-lhe Pipoca.", {"pet.cat.name": "Pipoca"}),
    ("The dog we have at home answers to Simba.", {"pet.dog.name": "Simba"}),
    ("O cão que temos em casa responde por Simba.", {"pet.dog.name": "Simba"}),
    ("I live in Matola with my wife Telma.", {"identity.location": "Matola", "family.partner_name": "Telma"}),
    ("Moro na Matola com a minha esposa Telma.", {"identity.location": "Matola", "family.partner_name": "Telma"}),
    ("My car location link is https://track.example.test/v/3", {"asset.car_location_link": "https://track.example.test/v/3"}),
    ("New update: my car location link is now https://track.example.test/v/9", {"asset.car_location_link": "https://track.example.test/v/9"}),
    ("Actualização: o link da localização do meu carro passou a ser https://track.example.test/v/10", {"asset.car_location_link": "https://track.example.test/v/10"}),
]


@pytest.mark.parametrize("text,expect", CASES, ids=[c[0][:40] for c in CASES])
def test_unseen_moulds_write_exactly_the_stated_facts(tmp_path, text, expect):
    assert _run(tmp_path / "m", text) == expect


def test_second_dog_and_appositions(tmp_path):
    assert _run(tmp_path / "s", "I got a second dog; her name is Nala.", prior=["My dog is Simba."]) == {"pet.dog.name.2": "Nala"}
    assert _run(tmp_path / "a", "My dog Simba is a rescue.", prior=["My dog is Simba."]) == {}          # apposition: no "rescue" name
    assert _run(tmp_path / "b", "My dog Simba is a rescue.") == {"pet.dog.name": "Simba"}
    assert _run(tmp_path / "c", "Esquece o que disse: chamo-me Marta Sitoe, não Marta Sitole.", prior=["Chamo-me Marta Sitole."]) == {"identity.name": "Marta Sitoe"}
